# Audit Report: tSendMail / SendMailComponent

> **Audited**: 2026-03-21
> **Auditor**: Claude Opus 4.6 (automated)
> **Engine Version**: v1
> **Converter**: `complex_converter`
> **Status**: PRODUCTION READINESS REVIEW

---

## 1. Component Identity

| Field | Value |
|-------|-------|
| **Talend Name** | `tSendMail` |
| **V1 Engine Class** | `SendMailComponent` |
| **Engine File** | `src/v1/engine/components/control/send_mail.py` (252 lines) |
| **Converter Parser** | `src/converters/complex_converter/component_parser.py` -> `parse_tsendmail()` (lines 1136-1152) |
| **Converter Dispatch** | `src/converters/complex_converter/converter.py` -> dedicated `elif component_type == 'tSendMail'` branch (line 264) |
| **Registry Aliases** | `SendMailComponent`, `tSendMail` (registered in `src/v1/engine/engine.py` lines 179-180) |
| **Category** | Control / Internet |

### Key Files

| File | Purpose |
|------|---------|
| `src/v1/engine/components/control/send_mail.py` | Engine implementation (252 lines) |
| `src/converters/complex_converter/component_parser.py` (lines 1136-1152) | Parameter mapping from Talend XML to v1 JSON -- dedicated `parse_tsendmail()` method |
| `src/converters/complex_converter/converter.py` (line 264) | Dispatch -- dedicated `elif` branch for `tSendMail` |
| `src/v1/engine/base_component.py` | Base class: `_update_stats()`, `_update_global_map()`, `validate_schema()`, `execute()` |
| `src/v1/engine/global_map.py` | GlobalMap storage for `{id}_NB_LINE` etc. |
| `src/v1/engine/exceptions.py` | Custom exception hierarchy (`ComponentExecutionError`, `ConfigurationError`, `FileOperationError`) |
| `src/v1/engine/components/control/__init__.py` | Package exports (line 4: `from .send_mail import SendMailComponent`) |

---

## 2. Scorecard

| Dimension | Score | P0 | P1 | P2 | P3 | Details |
|-----------|-------|----|----|----|----|---------|
| Converter Coverage | **Y** | 0 | 3 | 3 | 2 | 12 of 22 Talend params extracted (55%); missing IMPORTANCE, ENCODING, MIME_SUBTYPE, SHOW_SENDER_NAME, SET_LOCALHOST, OTHER_HEADERS, ATTACHMENTS table, DIE_IF_ATTACHMENT_DOESNT_EXIST, CUSTOM_HEADERS, NEED_AUTH toggle |
| Engine Feature Parity | **Y** | 0 | 4 | 4 | 2 | No importance header; no MIME subtype; no sender name display; no OAuth2; no custom headers; hardcoded attachment content type; no attachment encoding options |
| Code Quality | **Y** | 2 | 6 | 5 | 2 | Cross-cutting base class bugs; duplicate `validate_config()` methods (public + private); no `_update_global_map()` for ERROR_MESSAGE; SMTP connection not in context manager; attachment filename path leak; SSL+STARTTLS mutual exclusion not validated; FileOperationError re-wrapped by outer catch; success reported after silent failure; Content-Disposition filename not RFC 2183 quoted; dead code `validate_config()`; inconsistent `from_email` naming |
| Security | **Y** | 0 | 3 | 2 | 0 | SMTP credentials logged; password plain text in config; SMTP header injection via unsanitized fields; attachment path not sanitized; attachment filename leaks server path |
| Performance & Memory | **G** | 0 | 0 | 2 | 1 | No SMTP connection pooling; large attachment loaded entirely into memory; `msg.as_string()` creates second in-memory copy (~3-4x attachment size) |
| Testing | **R** | 1 | 1 | 0 | 0 | Zero v1 unit tests; zero v1 integration tests for this component |

**Overall: YELLOW -- Not production-ready without P0/P1 fixes**

### Score Key
- **R** (Red): Critical gaps blocking production use
- **Y** (Yellow): Significant gaps; usable for subset of jobs with known limitations
- **G** (Green): Production-ready with minor improvements recommended

---

## 3. Talend Feature Baseline

### What tSendMail Does

`tSendMail` sends email messages directly from a Talend job using the Simple Mail Transfer Protocol (SMTP). It is the primary component for email notifications, alerts, and report delivery in Talend data integration jobs. The component supports multiple recipients (To, CC, BCC), file attachments, HTML/plain text bodies, SSL/TLS encryption, SMTP authentication (Basic and OAuth2), custom headers, and configurable message priority/importance.

**Source**: [tSendMail Standard Properties (Talend 8.0)](https://help.qlik.com/talend/en-US/components/8.0/mail/tsendmail-standard-properties), [tSendMail Standard Properties (Talend 7.3)](https://help.qlik.com/talend/en-US/components/7.3/mail/tsendmail-standard-properties), [tSendMail Component Overview](https://help.qlik.com/talend/en-US/components/8.0/mail/tsendmail), [tSendMail by Example](https://www.talendbyexample.com/talend-tsendmail-component.html)

**Component family**: Internet / Mail
**Available in**: All Talend products (Standard, Big Data, Cloud, ESB).
**Required JARs**: `javax.mail.jar` (JavaMail API), `activation.jar`

### 3.1 Basic Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 1 | To | `TO` | Expression (String) | -- | **Mandatory**. Main recipient email address(es). Multiple addresses separated by semicolons or commas. Supports context variables and globalMap references. |
| 2 | From | `FROM` | Expression (String) | -- | **Mandatory**. Sender email address. Must be a valid email format. |
| 3 | Show sender's name | `SHOW_SENDER_NAME` | Boolean (CHECK) | `false` | When enabled, displays a human-readable sender name in the "From" header alongside the email address. |
| 4 | Sender Name | `SENDER_NAME` | Expression (String) | -- | Human-readable name displayed as sender. Only visible when `SHOW_SENDER_NAME=true`. |
| 5 | Cc | `CC` | Expression (String) | -- | Email addresses of secondary (carbon copy) recipients. Multiple addresses separated by semicolons or commas. |
| 6 | Bcc | `BCC` | Expression (String) | -- | Email addresses of blind carbon copy recipients. Not visible to other recipients. Multiple addresses separated by semicolons or commas. |
| 7 | Subject | `SUBJECT` | Expression (String) | -- | Email subject line. Supports context variables and globalMap references via Ctrl+Space. |
| 8 | Message | `MESSAGE` | Expression (String) | -- | Email body content. Supports context variables, globalMap references, and Java expressions. Can contain HTML when MIME subtype is set to `html`. |
| 9 | Die if attachment doesn't exist | `DIE_IF_ATTACHMENT_DOESNT_EXIST` | Boolean (CHECK) | `true` | When enabled, the job fails if any attachment file path does not exist. When unchecked, missing attachments are skipped and the email is sent without them. |
| 10 | Attachments | `ATTACHMENTS` | Table (FILE, ENCODING) | -- | Table of file attachments. Each row specifies a file path (String expression) and a content transfer encoding (Base64, 7bit, 8bit, quoted-printable, binary). |
| 11 | Other Headers | `OTHER_HEADERS` | Table (KEY, VALUE) | -- | Custom key-value header pairs added to the email message (e.g., `Reply-To`, `X-Custom-Header`). |
| 12 | SMTP Host | `SMTP_HOST` | Expression (String) | -- | **Mandatory**. IP address or hostname of the SMTP server (e.g., `smtp.gmail.com`, `smtp.office365.com`). |
| 13 | SMTP Port | `SMTP_PORT` | Expression (Integer) | `25` | SMTP server port. Common values: 25 (plain SMTP), 465 (SMTPS/SSL), 587 (submission/STARTTLS). |
| 14 | SSL Support | `SSL` | Boolean (CHECK) | `false` | Enable SSL/TLS encryption for the SMTP connection. Uses `SMTP_SSL` (implicit TLS on port 465). Mutually exclusive with STARTTLS in typical usage. |
| 15 | STARTTLS Support | `STARTTLS` | Boolean (CHECK) | `false` | Enable STARTTLS upgrade for the SMTP connection. Starts as plain connection then upgrades to TLS. Typically used with port 587. |
| 16 | Importance | `IMPORTANCE` | Dropdown | `Normal` | Email priority/importance level. Options: `High`, `Normal`, `Low`. Sets the `Importance` and `X-Priority` headers. |
| 17 | Authentication mode | `NEED_AUTH` / `AUTH_METHOD` | Dropdown | `No Auth` | Authentication method for the SMTP server. Options: `No Auth`, `Basic` (username/password), `OAuth2`. |
| 18 | Auth Username | `AUTH_USERNAME` | Expression (String) | -- | SMTP authentication username. Only visible when `NEED_AUTH` is `Basic`. |
| 19 | Auth Password | `AUTH_PASSWORD` | Expression (String / Password) | -- | SMTP authentication password. Stored encrypted in Talend metadata. Only visible when `NEED_AUTH` is `Basic`. |
| 20 | Die on error | `DIE_ON_ERROR` | Boolean (CHECK) | `true` | Stop the entire job on email sending error. When unchecked, the error is logged but the job continues. |

### 3.2 Advanced Settings

| # | Parameter | Talend XML Name | Type | Default | Description |
|---|-----------|-----------------|------|---------|-------------|
| 21 | MIME subtype | `MIME_SUBTYPE` | Dropdown | `plain` | Text MIME subtype. Options: `plain` (plain text), `html` (HTML formatted). Controls the Content-Type header of the email body. |
| 22 | Encoding type | `ENCODING` | Dropdown / Custom | `UTF-8` | Character encoding for the email body. Options include `UTF-8`, `ISO-8859-1`, `US-ASCII`, and custom values. |
| 23 | Set localhost | `SET_LOCALHOST` | Boolean (CHECK) | `false` | Specify a custom local hostname for the EHLO/HELO command sent to the SMTP server. Useful when the system hostname is not resolvable. |
| 24 | Localhost name | `LOCALHOST_NAME` | Expression (String) | -- | Custom hostname to use in EHLO/HELO. Only visible when `SET_LOCALHOST=true`. |
| 25 | OAuth2 two-line auth | `OAUTH2_TWO_LINE` | Boolean (CHECK) | `false` | Enhanced OAuth2 authentication method for services that require two-line authorization. |
| 26 | Custom properties | `CUSTOM_PROPERTIES` | Table (KEY, VALUE) | -- | User-defined key-value pairs for JavaMail session properties. Allows fine-grained SMTP configuration (e.g., `mail.smtp.timeout`, `mail.smtp.connectiontimeout`). |
| 27 | tStatCatcher Statistics | `TSTATCATCHER_STATS` | Boolean (CHECK) | `false` | Capture processing metadata for the tStatCatcher component. Rarely used. |
| 28 | Property Type | `PROPERTY_TYPE` | Built-In / Repository | Built-In | Whether config comes from metadata repository or is inline. Not needed at runtime. |

### 3.3 Connection Types

| Connector | Direction | Type | Description |
|-----------|-----------|------|-------------|
| `SUBJOB_OK` | Output (Trigger) | Trigger | Fires when the entire subjob containing this component completes successfully. Used for chaining subjobs. |
| `SUBJOB_ERROR` | Output (Trigger) | Trigger | Fires when the subjob containing this component fails with an error. Used for error handling flows. |
| `COMPONENT_OK` | Output (Trigger) | Trigger | Fires when this specific component completes execution successfully. More granular than SUBJOB_OK. |
| `COMPONENT_ERROR` | Output (Trigger) | Trigger | Fires when this specific component fails with an error. More granular than SUBJOB_ERROR. |
| `RUN_IF` | Output (Trigger) | Trigger | Conditional trigger with a boolean expression. The target component only executes if the condition evaluates to true. |

**Note**: tSendMail does NOT have FLOW (Row) connections. It is a standalone action component that does not receive or produce data rows. It is typically triggered by `SUBJOB_OK`, `COMPONENT_OK`, `COMPONENT_ERROR`, or `RUN_IF` triggers from upstream components.

### 3.4 GlobalMap Variables

| Variable Pattern | Type | When Set | Description |
|------------------|------|----------|-------------|
| `{id}_ERROR_MESSAGE` | String | After execution (on error) | Error message string containing details of the SMTP failure. Available for reference in downstream error handling flows. |

**Note on NB_LINE**: Unlike data-processing components, `tSendMail` does NOT set `NB_LINE`, `NB_LINE_OK`, or `NB_LINE_REJECT` because it does not process data rows. The only meaningful global variable is `ERROR_MESSAGE`.

**Note on ERROR_MESSAGE usage**: Community forums confirm that `((String)globalMap.get("tSendMail_1_ERROR_MESSAGE"))` is commonly used in downstream components to capture and log SMTP failures. This is the primary mechanism for email error reporting in Talend jobs.

### 3.5 Behavioral Notes

1. **No data flow**: `tSendMail` is a control/action component. It does not have input or output Row connections. It is triggered via OnSubjobOk, OnComponentOk, OnComponentError, OnSubjobError, or RunIf triggers.

2. **Recipient separator**: Talend accepts multiple email addresses separated by semicolons (`;`) or commas (`,`) in the To, Cc, and Bcc fields. The component splits on these delimiters internally.

3. **SSL vs STARTTLS**: SSL (`SSL=true`) establishes a fully encrypted connection from the start (typically port 465). STARTTLS (`STARTTLS=true`) upgrades a plain connection to encrypted (typically port 587). These are NOT mutually exclusive in the Talend UI -- a user could theoretically enable both -- but doing so is undefined behavior and will typically cause connection failures.

4. **Attachment encoding**: Each attachment in the Attachments table has its own content transfer encoding setting (Base64, 7bit, 8bit, quoted-printable, binary). Base64 is the most common choice for binary files.

5. **Importance header mapping**: The Importance dropdown maps to standard email headers:
   - `High` -> `Importance: High`, `X-Priority: 1`
   - `Normal` -> `Importance: Normal`, `X-Priority: 3`
   - `Low` -> `Importance: Low`, `X-Priority: 5`

6. **Die if attachment doesn't exist**: When enabled (default), a missing attachment file causes the entire job to fail before the email is sent. When disabled, the email is sent without the missing attachment, and a warning is logged.

7. **HTML email**: To send HTML-formatted email, set `MIME_SUBTYPE` to `html` and write HTML markup in the Message field. The Content-Type header is set to `text/html`.

8. **Context variable best practice**: Talend recommends using context variables for all SMTP configuration (host, port, username, password, recipients) to enable environment-specific overrides without modifying the job.

9. **Password security**: The `AUTH_PASSWORD` field stores passwords encrypted in the Talend repository. At runtime, passwords are decrypted by the Talend engine. In exported job scripts, passwords may appear as encrypted strings or context variable references.

10. **OAuth2 authentication**: Newer Talend versions (7.x+) support OAuth2 authentication for services like Gmail and Office 365. This requires configuring OAuth2 tokens and refresh flows outside the component.

11. **Custom properties**: The `CUSTOM_PROPERTIES` table allows setting JavaMail session properties directly, such as `mail.smtp.timeout=30000` for connection timeout or `mail.smtp.auth.mechanisms=XOAUTH2` for specific auth mechanisms.

12. **Error handling pattern**: In production Talend jobs, tSendMail is most commonly used at the END of error handling flows, connected via `OnSubjobError` or `OnComponentError` triggers. The message body typically contains `((String)globalMap.get("component_ERROR_MESSAGE"))` to include error details.

---

## 4. Converter Audit

### 4.1 Parameter Extraction

The converter uses a **dedicated `parse_tsendmail()` method** in `component_parser.py` (lines 1136-1152). This is properly dispatched via a dedicated `elif component_type == 'tSendMail'` branch in `converter.py` (line 264). This follows STANDARDS.md requirements for dedicated parser methods.

**Converter flow**:
1. `converter.py:_parse_component()` identifies `component_type == 'tSendMail'` (line 264)
2. Calls `self.component_parser.parse_tsendmail(node, component)` (line 265)
3. `parse_tsendmail()` extracts parameters via direct XPath `node.find('.//elementParameter[@name="..."]')` queries
4. Returns component dict with populated `config` dictionary

| # | Talend XML Parameter | Extracted? | V1 Config Key | Converter Line | Notes |
|----|----------------------|------------|---------------|----------------|-------|
| 1 | `SMTP_HOST` | Yes | `smtp_host` | 1138 | Direct XPath extraction. No null check on `node.find()`. |
| 2 | `SMTP_PORT` | Yes | `smtp_port` | 1139 | **`int()` cast with no error handling.** Will crash if value is non-numeric or context variable. |
| 3 | `FROM` | Yes | `from_email` | 1140 | Direct extraction. Renamed from `FROM` to `from_email`. |
| 4 | `TO` | Yes | `to` | 1141 | Split on `;` to create list. `.strip()` on each element. |
| 5 | `CC` | Yes | `cc` | 1142 | Split on `;` to create list. `.strip()` on each element. |
| 6 | `BCC` | Yes | `bcc` | 1143 | Split on `;` to create list. `.strip()` on each element. |
| 7 | `SUBJECT` | Yes | `subject` | 1144 | Direct extraction. |
| 8 | `MESSAGE` | Yes | `message` | 1145 | Direct extraction. Java expressions in message body NOT marked with `{{java}}`. |
| 9 | `SSL` | Yes | `ssl` | 1147 | Boolean from string comparison `.lower() == 'true'`. |
| 10 | `STARTTLS` | Yes | `starttls` | 1148 | Boolean from string comparison. |
| 11 | `AUTH_USERNAME` | Yes | `auth_username` | 1149 | Direct extraction. |
| 12 | `AUTH_PASSWORD` | Yes | `auth_password` | 1150 | Direct extraction. **Password stored in plain text in v1 JSON config.** |
| 13 | `DIE_ON_ERROR` | Yes | `die_on_error` | 1151 | Boolean from string comparison. Default `true` matches Talend. |
| 14 | `ATTACHMENTS` | **Partial** | `attachments` | 1146 | **Hardcoded to empty list `[]`.** Table parameter not parsed at all. Attachment file paths and encodings are lost. |
| 15 | `IMPORTANCE` | **No** | -- | -- | **Not extracted. Email priority not configurable.** |
| 16 | `MIME_SUBTYPE` | **No** | -- | -- | **Not extracted. Cannot send HTML email.** |
| 17 | `ENCODING` | **No** | -- | -- | **Not extracted. Engine hardcodes UTF-8.** |
| 18 | `SHOW_SENDER_NAME` | **No** | -- | -- | **Not extracted.** |
| 19 | `SENDER_NAME` | **No** | -- | -- | **Not extracted.** |
| 20 | `OTHER_HEADERS` | **No** | -- | -- | **Not extracted. Table parameter. Custom headers lost.** |
| 21 | `SET_LOCALHOST` | **No** | -- | -- | **Not extracted.** |
| 22 | `LOCALHOST_NAME` | **No** | -- | -- | **Not extracted.** |
| 23 | `NEED_AUTH` | **No** | -- | -- | **Not extracted. Auth enabled implicitly by presence of username/password.** |
| 24 | `DIE_IF_ATTACHMENT_DOESNT_EXIST` | **No** | -- | -- | **Not extracted. Engine uses `die_on_error` for attachment failures instead.** |
| 25 | `CUSTOM_PROPERTIES` | **No** | -- | -- | **Not extracted. Table parameter.** |
| 26 | `OAUTH2_TWO_LINE` | **No** | -- | -- | **Not extracted. OAuth2 not supported.** |
| 27 | `TSTATCATCHER_STATS` | **No** | -- | -- | Not extracted (low priority -- tStatCatcher rarely used). |
| 28 | `PROPERTY_TYPE` | No | -- | -- | Not needed (always Built-In in converted jobs). |

**Summary**: 13 of 28 parameters extracted (46%). Of the 15 missing, 10 are runtime-relevant.

### 4.2 Schema Extraction

Not applicable. `tSendMail` does not have input or output schemas. It does not process data rows.

### 4.3 Expression Handling

**Context variable handling**: The `parse_tsendmail()` method uses direct `.get('value', '')` extraction without passing through the generic expression detection pipeline. This means:

- Context variables in SMTP_HOST, FROM, TO, SUBJECT, MESSAGE, etc. are extracted as raw strings (e.g., `context.smtp_host`)
- The base class `execute()` method calls `self.context_manager.resolve_dict(self.config)` (line 202 of `base_component.py`), which resolves `${context.var}` patterns
- However, the converter does NOT wrap context references as `${context.var}` -- they are left as bare `context.var` strings from the Talend XML
- Java expressions in MESSAGE body (e.g., string concatenation, globalMap references) are NOT detected or marked with `{{java}}` prefix

**Known limitations**:
- Java expressions within the `MESSAGE` field (common for dynamic error messages like `"Job failed: " + ((String)globalMap.get("tRunJob_1_ERROR_MESSAGE"))`) are stored as literal strings. They will NOT be evaluated at runtime.
- Password values may contain special characters that are not escaped during extraction.

### 4.4 Converter Issues

| ID | Priority | Issue |
|----|----------|-------|
| CONV-SM-001 | **P1** | **Attachments table not parsed**: `component['config']['attachments'] = []` (line 1146) hardcodes attachments to empty list. The Talend ATTACHMENTS table parameter with file paths and encoding options is completely ignored. Jobs relying on email attachments will send emails without any attachments. |
| CONV-SM-002 | **P1** | **No null checks on `node.find()`**: Every XPath query assumes the element exists (e.g., `node.find('.//elementParameter[@name="SMTP_HOST"]').get('value', '')`). If any parameter is missing from the Talend XML (optional parameters, older Talend versions), `node.find()` returns `None` and `.get()` raises `AttributeError: 'NoneType' object has no attribute 'get'`. The `parse_t_xml_map()` method (lines 1155-1169) demonstrates the correct pattern with explicit null checks. |
| CONV-SM-003 | **P1** | **`SMTP_PORT` cast crashes on non-integer**: `int(node.find(...)get('value', '25'))` (line 1139) will raise `ValueError` if the port value is a context variable (e.g., `context.smtp_port`) or Java expression. Should use safe conversion with fallback. |
| CONV-SM-004 | **P2** | **`IMPORTANCE` not extracted**: Email priority (High/Normal/Low) is dropped during conversion. All converted emails will have default priority regardless of Talend configuration. |
| CONV-SM-005 | **P2** | **`MIME_SUBTYPE` not extracted**: HTML email configuration is lost. Jobs that send HTML-formatted emails will send the HTML as plain text in the v1 engine (since engine defaults to `text_subtype='plain'`). |
| CONV-SM-006 | **P2** | **`ENCODING` not extracted**: Email encoding defaults to engine's UTF-8. Jobs using ISO-8859-1 or other encodings will produce emails with wrong Content-Type charset header. |
| CONV-SM-007 | **P3** | **Recipient split only on semicolon**: Lines 1141-1143 split recipients on `;` only. Talend also accepts `,` as separator. Recipient lists using comma-separated format will produce a single recipient containing commas. |
| CONV-SM-008 | **P3** | **`AUTH_PASSWORD` stored in plain text**: The converter extracts the password value as a plain string and writes it to the v1 JSON config file. Talend encrypts passwords in the repository. This is a security concern if v1 config files are committed to version control or stored in accessible locations. |

---

## 5. Engine Feature Parity

### 5.1 Feature Implementation Status

| # | Talend Feature | Implemented? | Fidelity | Engine Location | Notes |
|----|----------------|-------------|----------|-----------------|-------|
| 1 | Send email via SMTP | **Yes** | High | `_process()` lines 198-216 | Uses Python `smtplib` -- functionally equivalent to JavaMail |
| 2 | Multiple To recipients | **Yes** | High | `_process()` line 145, 213 | List of recipients, joined for header, expanded for sendmail |
| 3 | CC recipients | **Yes** | High | `_process()` lines 147, 162 | CC addresses set in header and included in all_recipients |
| 4 | BCC recipients | **Yes** | High | `_process()` lines 148, 213 | BCC included in sendmail recipients but NOT in message headers -- correct behavior |
| 5 | Subject line | **Yes** | High | `_process()` line 163 | Direct header assignment |
| 6 | Message body | **Yes** | High | `_process()` lines 166-171 | MIMEText with configurable subtype and encoding |
| 7 | File attachments | **Yes** | Medium | `_process()` lines 174-196 | Reads files, Base64 encodes, attaches. Missing: per-attachment encoding selection. |
| 8 | SSL connection | **Yes** | High | `_process()` lines 200-201 | Uses `smtplib.SMTP_SSL()` -- correct for implicit TLS |
| 9 | STARTTLS upgrade | **Yes** | High | `_process()` lines 205-207 | Calls `server.starttls()` after plain connection -- correct |
| 10 | Basic authentication | **Yes** | High | `_process()` lines 209-211 | `server.login(username, password)` -- correct |
| 11 | Die on error (SMTP) | **Yes** | High | `_process()` lines 220-226 | Raises `ComponentExecutionError` or logs warning based on flag |
| 12 | Die on error (attachment) | **Yes** | Medium | `_process()` lines 183-196 | Uses same `die_on_error` flag rather than separate `DIE_IF_ATTACHMENT_DOESNT_EXIST` |
| 13 | Text/HTML MIME subtype | **Yes** | Medium | `_process()` line 168 | Reads from `config.get('text_subtype', 'plain')`. Defaults to plain. Works IF converter extracted MIME_SUBTYPE. |
| 14 | Encoding | **Yes** | Medium | `_process()` line 169 | Reads from `config.get('encoding', 'utf-8')`. Defaults to UTF-8. Works IF converter extracted ENCODING. |
| 15 | Statistics tracking | **Yes** | Low | `_process()` line 235 | Sets (0, 0, 0) -- always zero since no data processing. Correct for non-data component. |
| 16 | **Importance header** | **No** | N/A | -- | **No `Importance` or `X-Priority` header set. All emails sent with default priority.** |
| 17 | **Show sender name** | **No** | N/A | -- | **No support for `From: "Display Name" <email@addr>`**. Only bare email address in From header. |
| 18 | **Other headers** | **No** | N/A | -- | **No custom header support. Reply-To, X-Custom-Header, etc. cannot be set.** |
| 19 | **OAuth2 authentication** | **No** | N/A | -- | **No OAuth2 support. Only Basic auth (username/password).** |
| 20 | **Set localhost (EHLO)** | **No** | N/A | -- | **No custom EHLO hostname. Uses system default.** |
| 21 | **Custom SMTP properties** | **No** | N/A | -- | **No JavaMail session property equivalents (timeouts, mechanisms).** |
| 22 | **Attachment encoding selection** | **No** | N/A | -- | **All attachments hardcoded to Base64 encoding. No 7bit/8bit/quoted-printable/binary options.** |
| 23 | **Die if attachment doesn't exist (separate toggle)** | **No** | N/A | -- | **Uses single `die_on_error` flag for both SMTP and attachment errors. Talend has separate toggles.** |
| 24 | **`{id}_ERROR_MESSAGE` globalMap** | **No** | N/A | -- | **Error message not stored in globalMap. See Section 5.3.** |

### 5.2 Behavioral Differences from Talend

| ID | Priority | Description |
|----|----------|-------------|
| ENG-SM-001 | **P1** | **No `{id}_ERROR_MESSAGE` in globalMap**: When email sending fails with `die_on_error=false`, Talend stores the error message in `globalMap.get("tSendMail_1_ERROR_MESSAGE")`. The v1 engine catches the exception and logs a warning (line 226) but does NOT call `self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(e))`. Downstream components referencing the error message will get null/None. This is the primary mechanism for SMTP error reporting in Talend jobs. |
| ENG-SM-002 | **P1** | **No Importance/Priority header**: The `Importance` and `X-Priority` headers are not set on outgoing emails. Emails configured as "High" priority in Talend will be sent as normal priority. For alert/notification workflows where email priority determines triage, this is a functional gap. |
| ENG-SM-003 | **P1** | **Attachment filename includes full path**: Line 181 uses `f'attachment; filename={attachment}'` where `attachment` is the full file path (e.g., `/data/reports/report.csv`). The attachment filename should be just the basename (`report.csv`). Recipients will see the full server path in the attachment name, which leaks internal path information. Talend uses just the filename. |
| ENG-SM-004 | **P1** | **SMTP connection not closed on error**: If an exception occurs AFTER `smtplib.SMTP()` connects (line 201/203) but BEFORE `server.quit()` (line 216), the SMTP connection is leaked. There is no `try/finally` or context manager (`with`) wrapping the server connection. In repeated failure scenarios, this can exhaust SMTP connection limits. |
| ENG-SM-005 | **P2** | **No sender display name support**: The `From` header is set to the bare email address (line 161: `msg['From'] = from_email`). Talend supports `"Display Name" <email@addr>` format via the `SHOW_SENDER_NAME` toggle. |
| ENG-SM-006 | **P2** | **No custom email headers**: No mechanism to add arbitrary headers like `Reply-To`, `X-Custom-Header`, or `List-Unsubscribe`. The `OTHER_HEADERS` table parameter from Talend is not supported. |
| ENG-SM-007 | **P2** | **No SMTP timeout configuration**: No connection or read timeouts are configured. If the SMTP server is unresponsive, the component will hang indefinitely (Python socket default). Talend allows timeout configuration via `CUSTOM_PROPERTIES` (`mail.smtp.timeout`). |
| ENG-SM-008 | **P2** | **All attachments use Base64 encoding**: Line 180 calls `encoders.encode_base64(part)` for every attachment. Talend allows per-attachment encoding selection (Base64, 7bit, 8bit, quoted-printable, binary). For text file attachments, 7bit encoding is more efficient and preserves readability. |
| ENG-SM-009 | **P3** | **No OAuth2 authentication**: Modern email services (Gmail, Office 365) increasingly require OAuth2. Only username/password Basic auth is supported. |
| ENG-SM-010 | **P3** | **No custom EHLO hostname**: The `SET_LOCALHOST` feature is not supported. Some SMTP servers reject connections with unresolvable hostnames. |

### 5.3 GlobalMap Variable Coverage

| Variable | Talend Sets? | V1 Sets? | How V1 Sets It | Notes |
|----------|-------------|----------|-----------------|-------|
| `{id}_NB_LINE` | No (non-data component) | **Yes** | `_update_stats(0, 0, 0)` -> `_update_global_map()` | Always 0. Not meaningful for this component. Talend does not set this. |
| `{id}_NB_LINE_OK` | No | **Yes** | Same mechanism | Always 0. Not meaningful. |
| `{id}_NB_LINE_REJECT` | No | **Yes** | Same mechanism | Always 0. Not meaningful. |
| `{id}_ERROR_MESSAGE` | **Yes** (official) | **No** | -- | **Not implemented. This is the ONLY meaningful globalMap variable for tSendMail. Critical gap.** |
| `{id}_EXECUTION_TIME` | N/A (v1 only) | **Yes** | Base class | V1-specific, not in Talend. |

---

## 6. Code Quality

### 6.1 Bugs

| ID | Priority | Location | Description |
|----|----------|----------|-------------|
| BUG-SM-001 | **P0** | `src/v1/engine/base_component.py:304` | **`_update_global_map()` references undefined variable `value`**: The log statement on line 304 uses `{stat_name}: {value}` but the variable in the for loop (line 301) is named `stat_value`, not `value`. This causes `NameError` at runtime whenever `global_map` is not None and `_update_global_map()` is called. Since `execute()` calls `_update_global_map()` on BOTH success (line 218) and error (line 231), this bug will crash SendMailComponent every time it runs with a globalMap. **CROSS-CUTTING**: Affects ALL components. |
| BUG-SM-002 | **P0** | `src/v1/engine/global_map.py:28` | **`GlobalMap.get()` references undefined `default` parameter**: The method signature is `def get(self, key: str) -> Optional[Any]` (line 26), but the body calls `self._map.get(key, default)` (line 28). The `default` parameter is not in the signature. Additionally, `get_component_stat()` on line 58 calls `self.get(key, default)` with two arguments, but `get()` only accepts one. This causes `NameError` on every `.get()` call. **CROSS-CUTTING**: Affects all code using `global_map.get()`. |
| BUG-SM-003 | **P1** | `src/v1/engine/components/control/send_mail.py:181` | **Attachment filename leaks full server path**: `part.add_header('Content-Disposition', f'attachment; filename={attachment}')` uses the full file path as the filename. If `attachment` is `/data/etl/reports/daily_report.csv`, the recipient sees this full path. Should use `os.path.basename(attachment)`. This is also a security concern as it exposes internal directory structure. |
| BUG-SM-004 | **P1** | `src/v1/engine/components/control/send_mail.py:198-216` | **SMTP connection leaked on error**: The SMTP server connection (lines 200-203) is not wrapped in a `try/finally` or `with` statement. If `server.starttls()` (line 207), `server.login()` (line 211), or `server.sendmail()` (line 215) raises an exception, `server.quit()` (line 216) is never called. The connection remains open until garbage collected. In high-volume error scenarios, this exhausts server connection limits. |
| BUG-SM-005 | **P1** | `src/v1/engine/components/control/send_mail.py:226-232` | **Swallowed exception on `die_on_error=false` for generic errors**: The second except block (lines 228-232) catches `Exception` when `die_on_error=true` but does NOT have an `else` branch for `die_on_error=false`. If `die_on_error=false` and an unexpected (non-SMTP) exception occurs, the exception propagates upward uncaught, bypassing the `die_on_error=false` intent. The first except block (lines 220-226) correctly handles both cases. |
| BUG-SM-006 | **P1** | `src/v1/engine/components/control/send_mail.py:82-114, 240-252` | **Duplicate validation methods -- public `validate_config()` and private `_validate_config()`**: The class defines two validation methods: `_validate_config()` (lines 82-114, called from `_process()` line 134) and `validate_config()` (lines 240-252, never called). The public `validate_config()` performs a subset of the validation (only checks 3 required fields, returns bool), while `_validate_config()` performs comprehensive validation (5 checks, returns list of errors). The public method is dead code. However, having two methods with the same purpose but different names and signatures creates maintenance risk. |
| BUG-SM-007 | **P2** | `src/v1/engine/components/control/send_mail.py:142-143` | **Empty CC/BCC creates `['']` list from empty string split**: When `cc` or `bcc` is an empty list `[]` from config but the converter sets it from an empty `value=''` split, `''.split(';')` produces `['']` (list with one empty string). Line 162 sets `msg['Cc'] = ', '.join(cc_emails)` which produces an empty `Cc:` header with no address. While functionally harmless for header display, line 213 `all_recipients = to_emails + cc_emails + bcc_emails` includes `''` (empty string) in the recipient list, which may cause SMTP `RCPT TO:<>` errors on strict servers. |
| BUG-SM-008 | **P1** | `src/v1/engine/components/control/send_mail.py:200-207` | **SSL + STARTTLS simultaneously causes crash**: When both `ssl=True` and `starttls=True`, `SMTP_SSL` creates an encrypted connection, then `starttls()` on the already-TLS connection raises `SMTPNotSupportedError`. `_validate_config()` does not check for this mutually exclusive configuration. |
| BUG-SM-009 | **P1** | `src/v1/engine/components/control/send_mail.py:186-194, 228-232` | **FileOperationError raised for attachment failures is caught by outer `except Exception`**: `FileOperationError` raised at lines 186-194 is caught by the outer `except Exception` block at lines 228-232 and re-wrapped as `ComponentExecutionError`. Caller loses the specific exception type, making it impossible to distinguish attachment errors from SMTP errors programmatically. |
| BUG-SM-010 | **P2** | `src/v1/engine/components/control/send_mail.py:220-238` | **Component reports success after failed send**: When `die_on_error=False`, the exception handler falls through to `_update_stats(0,0,0)` and `return {}`, making it impossible to distinguish a successful send from a silent failure. No status flag, return value, or globalMap entry differentiates the two outcomes. |
| BUG-SM-011 | **P3** | `src/v1/engine/components/control/send_mail.py:181` | **Content-Disposition filename not quoted per RFC 2183**: Filenames containing spaces, semicolons, or other special characters produce malformed `Content-Disposition` headers. The filename value must be quoted (e.g., `filename="my report.csv"`) to comply with RFC 2183. |

### 6.2 Naming Consistency

| ID | Priority | Issue |
|----|----------|-------|
| NAME-SM-001 | **P2** | **`from_email` vs Talend `FROM`**: Config key renamed from `FROM` to `from_email`. This is a reasonable rename since `from` is a Python reserved keyword, but it differs from the pattern used by other components where Talend names are preserved as snake_case (e.g., `smtp_host` for `SMTP_HOST`). |
| NAME-SM-002 | **P3** | **`ssl` (boolean) vs `use_ssl`**: The config key `ssl` is ambiguous -- it could mean the SSL version or a boolean enable flag. Talend uses `SSL` (capitalized). The engine variable is `use_ssl` (line 153), creating a naming split between config key and internal variable. |

### 6.3 Standards Compliance

| ID | Priority | Standard | Violation |
|----|----------|----------|-----------|
| STD-SM-001 | **P1** | "Every component MUST implement `_validate_config()` returning `List[str]`" (STANDARDS.md) | Component has `_validate_config()` AND it is called from `_process()` (line 134). This MEETS the standard. However, the duplicate `validate_config()` method (lines 240-252) violates the principle of having a single validation entry point. |
| STD-SM-002 | **P2** | "No dead code" (implicit standard) | `validate_config()` (lines 240-252) is never called by any code path. Dead code that duplicates `_validate_config()` logic. |
| STD-SM-003 | **P2** | "Return type from `_process()` should contain output data" | `_process()` returns `{}` (empty dict) on success (line 238). This is correct for a non-data component, but the empty dict lacks the `'main'` key that `execute()._execute_batch()` expects when appending results in streaming mode (`chunk_result.get('main')`). Since SendMail is a non-data component, streaming mode should never apply, so this is a theoretical rather than practical issue. |

### 6.4 Debug Artifacts

No debug artifacts, print statements, or commented-out code found in `send_mail.py`.

### 6.5 Security

| ID | Priority | Issue |
|----|----------|-------|
| SEC-SM-001 | **P1** | **SMTP credentials logged in debug output**: Line 210 logs `f"[{self.id}] Authenticating with username: {auth_username}"`. While the password itself is not logged, the username is. More critically, the base class `_resolve_java_expressions()` (line 148) logs ALL config values including password: `logger.info(f"Component {self.id}: Executing Java Expressions: {java_expressions}")`. If `auth_password` contains a `{{java}}` marker, the password expression is logged at INFO level. |
| SEC-SM-002 | **P1** | **Password stored in plain text in v1 JSON config**: The converter extracts `AUTH_PASSWORD` as a plain string (line 1150) and the engine reads it from config (line 152). In Talend, passwords are encrypted in the repository. The v1 config file contains the password in cleartext, creating a security risk if config files are in version control, shared storage, or log files. |
| SEC-SM-003 | **P1** | **SMTP header injection via unsanitized Subject, To, CC, BCC fields**: Values from config are assigned directly to email headers (lines 160-163) with zero sanitization. Newline characters in these fields can inject arbitrary headers (e.g., `Subject: test\r\nBcc: evil@attacker.com`). An attacker who controls any header field value can add arbitrary recipients, override headers, or inject email body content. |
| SEC-SM-004 | **P2** | **Attachment path not sanitized**: The `attachment` file path (line 178) is used directly in `open(attachment, 'rb')`. If config is tampered with, arbitrary files can be read and attached to emails. For Talend-converted jobs this is low risk (config is trusted), but noted for defense-in-depth. |
| SEC-SM-005 | **P2** | **Attachment filename leaks server path**: See BUG-SM-003. Full file path exposed to email recipients. |

### 6.6 Logging Quality

| Aspect | Assessment |
|--------|------------|
| Logger setup | Module-level `logger = logging.getLogger(__name__)` -- correct |
| Component ID prefix | All log messages use `[{self.id}]` prefix -- correct |
| Level usage | INFO for start/complete, DEBUG for details, WARNING for recoverable issues, ERROR for failures -- correct |
| Start/complete logging | `_process()` logs start (line 131) and complete (line 236) -- correct |
| Sensitive data | Username logged at DEBUG (line 210). Password NOT directly logged. But see SEC-SM-001 for indirect exposure. |
| No print statements | No `print()` calls -- correct |
| Recipient count | Logged at DEBUG (line 158, 214) -- good for debugging without exposing addresses |

### 6.7 Error Handling Quality

| Aspect | Assessment |
|--------|------------|
| Custom exceptions | Uses `ConfigurationError`, `FileOperationError`, and `ComponentExecutionError` from `exceptions.py` -- correct |
| Exception chaining | Uses `raise ... from e` pattern consistently (lines 187, 194, 224, 232) -- correct |
| `die_on_error` handling | Attachment errors: handled correctly with both die and skip paths (lines 183-196). SMTP errors: first block correct (lines 220-226). Second block (lines 228-232) has missing else branch for `die_on_error=false` -- see BUG-SM-005. |
| Specific exception types | First catch block targets `(smtplib.SMTPException, ConnectionError, OSError)` (line 220) -- good specificity. Second catch block is `Exception` (line 228) -- acceptable as catch-all. |
| Error messages | Include component ID, operation description, and original error -- correct |
| Graceful degradation | With `die_on_error=false`, SMTP errors produce warning log and continue. Attachment errors skip missing files. -- correct |

### 6.8 Type Hints

| Aspect | Assessment |
|--------|------------|
| Method signatures | `_validate_config() -> List[str]`, `_process(...) -> Dict[str, Any]`, `validate_config() -> bool` -- correct |
| Parameter types | `_process(self, input_data: Optional[Any] = None)` -- correct |
| Complex types | Uses `Dict[str, Any]`, `List[str]`, `Optional[Any]` -- correct |
| Import completeness | Imports `Any, Dict, List, Optional` from typing -- correct |

### 6.9 Thread Safety

| Aspect | Assessment |
|--------|------------|
| Instance state | Component is stateful (stores `self.config`, `self.stats`). Each execution modifies instance state. NOT safe for concurrent use of the same instance. |
| SMTP connection | Connection created and destroyed within `_process()` -- no shared connection state. Safe for concurrent use of different instances. |
| GlobalMap access | `global_map.put()` and `global_map.get()` are not thread-safe (plain dict). Concurrent component execution could produce race conditions on globalMap. CROSS-CUTTING issue. |

---

## 7. Performance & Memory

| ID | Priority | Issue |
|----|----------|-------|
| PERF-SM-001 | **P2** | **Entire attachment loaded into memory**: Line 179 `file.read()` reads the entire attachment file into memory. For large attachments (hundreds of MB), this causes memory pressure. Python's `email` library does not support streaming attachment encoding. Mitigation: warn or reject attachments above a configurable size threshold. |
| PERF-SM-002 | **P3** | **No SMTP connection pooling**: Each `_process()` call creates a new SMTP connection (connect, auth, send, quit). For jobs that send many emails in a loop (e.g., per-row notifications via tFlowToIterate), each iteration pays the full connection setup/teardown cost. Consider connection caching for repeated sends. |
| PERF-SM-003 | **P2** | **`msg.as_string()` creates second complete in-memory copy**: Line 215 calls `msg.as_string()` which serializes the entire message including base64-encoded attachments into a new string. Base64 encoding expands binary data by ~33%, so the serialized string is larger than the original attachments. Total memory usage is 3-4x the attachment size (original binary + base64 MIMEBase payload + serialized string), not 1x as might be assumed from the single `file.read()` call. |

### 7.1 Memory Management Assessment

| Aspect | Assessment |
|--------|------------|
| Streaming mode | Not applicable. SendMail does not process data rows. `_auto_select_mode()` will always return BATCH since `input_data` is None. |
| Memory threshold | Not applicable (no data processing). |
| Attachment memory | Entire file read into memory (line 179). No streaming for large attachments. Additionally, `msg.as_string()` (line 215) creates a second complete copy of the serialized message including base64 payloads. Total memory: 3-4x attachment size (see PERF-SM-003). |
| Message body | In-memory string. No concern for typical email body sizes. |

### 7.2 HYBRID Streaming Mode Behavior

| Issue | Description |
|-------|-------------|
| Mode selection | `execute()` calls `_auto_select_mode(None)` which returns BATCH (line 238-239 of base_component.py). SendMail always runs in BATCH mode. |
| Streaming path | If somehow invoked in streaming mode, `_execute_streaming(None)` delegates to `_process(None)` (line 258 of base_component.py). Correct behavior -- no chunking for null input. |
| Non-data return | `_process()` returns `{}` (empty dict). `_execute_batch()` returns this directly. No issue. In streaming mode, `chunk_result.get('main')` returns None, so `results` stays empty, final return is `{'main': pd.DataFrame()}`. Harmless. |

---

## 8. Testing

### 8.1 Current Coverage

| Test Type | Exists? | File | Notes |
|-----------|---------|------|-------|
| V1 engine unit tests | **No** | -- | Zero test files found for `SendMailComponent` v1 engine component |
| V1 engine integration tests | **No** | -- | No v1 engine integration tests found for `SendMailComponent` |
| Converter tests | **No** | -- | No tests for `parse_tsendmail()` converter method |

**Key finding**: The v1 engine has ZERO tests for this component. All 252 lines of v1 engine code and 17 lines of converter code are completely unverified.

### 8.2 Recommended Test Cases

#### P0 -- Must Have Before Production

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 1 | Basic email send (mocked SMTP) | P0 | Mock `smtplib.SMTP`, send email with to/from/subject/message. Verify `sendmail()` called with correct args. |
| 2 | Missing required config | P0 | Omit `smtp_host`, verify `ConfigurationError` raised with descriptive message. |
| 3 | Missing `to` list | P0 | Provide empty or missing `to`, verify `ConfigurationError` raised. |
| 4 | Die on error = true + SMTP failure | P0 | Mock SMTP to raise `SMTPException`. Verify `ComponentExecutionError` raised. |
| 5 | Die on error = false + SMTP failure | P0 | Mock SMTP to raise `SMTPException`. Verify no exception, warning logged. |
| 6 | Statistics always zero | P0 | After execution, verify `stats['NB_LINE'] == 0`, `stats['NB_LINE_OK'] == 0`, `stats['NB_LINE_REJECT'] == 0`. |
| 7 | Return value is empty dict | P0 | Verify `_process()` returns `{}`. |

#### P1 -- Important

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 8 | SSL connection | P1 | Config `ssl=true`. Verify `smtplib.SMTP_SSL` used instead of `smtplib.SMTP`. |
| 9 | STARTTLS connection | P1 | Config `starttls=true`. Verify `server.starttls()` called after connection. |
| 10 | Authentication | P1 | Config with `auth_username` and `auth_password`. Verify `server.login()` called with correct credentials. |
| 11 | CC and BCC recipients | P1 | Send with CC and BCC lists. Verify all recipients included in `sendmail()` call. Verify BCC NOT in message headers. |
| 12 | Attachment (existing file) | P1 | Provide valid attachment path. Verify attachment added to MIMEMultipart message with Base64 encoding. |
| 13 | Missing attachment + die_on_error=true | P1 | Provide non-existent attachment path. Verify `FileOperationError` raised. |
| 14 | Missing attachment + die_on_error=false | P1 | Provide non-existent attachment path. Verify email sent WITHOUT attachment, warning logged. |
| 15 | HTML email body | P1 | Config with `text_subtype='html'`. Verify MIMEText created with subtype 'html'. |
| 16 | Custom encoding | P1 | Config with `encoding='iso-8859-1'`. Verify MIMEText created with correct charset. |
| 17 | Context variable resolution | P1 | Config with `smtp_host='${context.smtp_host}'`. Verify context manager resolves before SMTP connection. |
| 18 | GlobalMap integration | P1 | Execute with globalMap. Verify stats written (even though always 0). |
| 19 | Validate config -- invalid port | P1 | Config with `smtp_port=99999`. Verify `_validate_config()` returns error. |
| 20 | Validate config -- non-list `to` | P1 | Config with `to='single@email.com'` (string not list). Verify error. |

#### P2 -- Hardening

| # | Test Case | Priority | Description |
|----|-----------|----------|-------------|
| 21 | Empty CC produces no errors | P2 | Config with `cc=[]`. Verify `Cc:` header is empty string and no SMTP error. |
| 22 | Multiple attachments | P2 | Provide 3 attachment paths. Verify all attached to message. |
| 23 | Large attachment (>10MB) | P2 | Memory test: attach large file, verify no OOM for reasonable sizes. |
| 24 | Connection timeout simulation | P2 | Mock SMTP connect to raise `ConnectionError`. Verify `die_on_error` handling. |
| 25 | SSL + STARTTLS both true | P2 | Verify behavior (expected: SSL used, STARTTLS silently skipped or error). |
| 26 | Unicode in subject and body | P2 | Send email with non-ASCII characters. Verify encoding works. |
| 27 | Converter: parse_tsendmail | P2 | Unit test XML parsing: verify all 13 extracted parameters mapped correctly. |
| 28 | Converter: missing XML element | P2 | Provide XML without `SMTP_HOST` element. Verify converter crashes (documents current behavior). |

---

## 9. Issues Summary

### P0 -- Critical

| ID | Category | Summary |
|----|----------|---------|
| BUG-SM-001 | Bug (Cross-Cutting) | `_update_global_map()` in `base_component.py:304` references undefined variable `value` (should be `stat_value`). Will crash ALL components when `global_map` is set. |
| BUG-SM-002 | Bug (Cross-Cutting) | `GlobalMap.get()` in `global_map.py:28` references undefined parameter `default`. Will crash on any `global_map.get()` call. `get_component_stat()` also passes two args to single-arg `get()`. |
| TEST-SM-001 | Testing | Zero v1 unit tests for SendMailComponent. All 252 lines of engine code and 17 lines of converter code are unverified. |

### P1 -- Major

| ID | Category | Summary |
|----|----------|---------|
| CONV-SM-001 | Converter | Attachments table not parsed -- hardcoded to `[]`. Jobs with email attachments will send without them. |
| CONV-SM-002 | Converter | No null checks on `node.find()` XPath queries. Missing XML elements cause `AttributeError` crash. |
| CONV-SM-003 | Converter | `SMTP_PORT` `int()` cast crashes on context variables or expressions. |
| ENG-SM-001 | Engine | `{id}_ERROR_MESSAGE` not set in globalMap. Downstream error handling gets null. This is the ONLY meaningful globalMap variable for tSendMail. |
| ENG-SM-002 | Engine | No `Importance` / `X-Priority` headers. All emails sent at default priority. |
| ENG-SM-003 | Engine | Attachment `Content-Disposition` filename includes full server path. Leaks internal paths and produces ugly filenames. |
| ENG-SM-004 | Engine | SMTP connection not closed on error. No `try/finally` or `with` statement around server connection. Connection leak risk. |
| BUG-SM-003 | Bug | Attachment filename leaks full server path (also an engine gap). |
| BUG-SM-004 | Bug | SMTP connection leaked on error (no cleanup). |
| BUG-SM-005 | Bug | Generic `Exception` handler (lines 228-232) missing `die_on_error=false` else branch. Unexpected errors bypass die-on-error intent. |
| BUG-SM-006 | Bug | Duplicate validation methods: `_validate_config()` (active, comprehensive) and `validate_config()` (dead code, subset). Maintenance risk and confusion. |
| BUG-SM-008 | Bug | SSL + STARTTLS simultaneously causes crash. `SMTP_SSL` creates encrypted connection, then `starttls()` raises `SMTPNotSupportedError`. `_validate_config()` does not check mutual exclusion. |
| BUG-SM-009 | Bug | `FileOperationError` raised for attachment failures is caught by outer `except Exception` and re-wrapped as `ComponentExecutionError`. Caller loses specific exception type. |
| SEC-SM-001 | Security | SMTP username logged at DEBUG. Password potentially logged through Java expression resolution at INFO level. |
| SEC-SM-002 | Security | AUTH_PASSWORD stored in plain text in v1 JSON config files. No encryption. |
| SEC-SM-003 | Security | SMTP header injection via unsanitized Subject, To, CC, BCC fields. Newline characters can inject arbitrary headers. |
| TEST-SM-002 | Testing | No integration test for SendMailComponent in a multi-step v1 job with error handling triggers. |

### P2 -- Moderate

| ID | Category | Summary |
|----|----------|---------|
| CONV-SM-004 | Converter | `IMPORTANCE` not extracted. Email priority lost during conversion. |
| CONV-SM-005 | Converter | `MIME_SUBTYPE` not extracted. HTML email jobs send HTML as plain text. |
| CONV-SM-006 | Converter | `ENCODING` not extracted. Email charset defaults to UTF-8 regardless of Talend config. |
| ENG-SM-005 | Engine | No sender display name support. `From:` header only shows bare email address. |
| ENG-SM-006 | Engine | No custom email headers. `OTHER_HEADERS` table functionality missing. |
| ENG-SM-007 | Engine | No SMTP timeout configuration. Unresponsive server causes indefinite hang. |
| ENG-SM-008 | Engine | All attachments hardcoded to Base64 encoding. No per-attachment encoding selection. |
| BUG-SM-007 | Bug | Empty CC/BCC split produces `['']`, adding empty string to recipient list. May cause SMTP errors on strict servers. |
| BUG-SM-010 | Bug | Component reports success after failed send. When `die_on_error=False`, exception handler falls through to `_update_stats(0,0,0)` and `return {}`, making it impossible to distinguish successful send from silent failure. |
| NAME-SM-001 | Naming | `from_email` rename from `FROM` is inconsistent with other parameter naming patterns. |
| STD-SM-002 | Standards | Dead code: `validate_config()` (public, lines 240-252) never called. Duplicates `_validate_config()`. |
| STD-SM-003 | Standards | `_process()` returns `{}` (no `'main'` key). Harmless for non-data component but inconsistent with base class contract. |
| SEC-SM-004 | Security | Attachment file path not sanitized. Arbitrary file read possible if config is tampered. |
| SEC-SM-005 | Security | Attachment filename leaks server path (overlaps with BUG-SM-003). |
| PERF-SM-001 | Performance | Entire attachment file loaded into memory. No size limit or streaming. |
| PERF-SM-003 | Performance | `msg.as_string()` creates second complete in-memory copy including base64-encoded attachments (~33% larger). Total memory: 3-4x attachment size. |

### P3 -- Low

| ID | Category | Summary |
|----|----------|---------|
| CONV-SM-007 | Converter | Recipient split only on semicolon. Comma-separated recipients not handled. |
| CONV-SM-008 | Converter | `AUTH_PASSWORD` stored in plain text in config (overlaps SEC-SM-002). |
| ENG-SM-009 | Engine | No OAuth2 authentication support. |
| ENG-SM-010 | Engine | No custom EHLO hostname (`SET_LOCALHOST`). |
| NAME-SM-002 | Naming | `ssl` config key is ambiguous -- could mean version or enable flag. |
| BUG-SM-011 | Bug | Content-Disposition filename not quoted per RFC 2183. Filenames with spaces/semicolons produce malformed headers. |
| PERF-SM-002 | Performance | No SMTP connection pooling for repeated sends. |

### Issue Count Summary

| Priority | Count | Categories |
|----------|-------|------------|
| P0 | 3 | 2 bugs (cross-cutting), 1 testing |
| P1 | 17 | 3 converter, 4 engine, 6 bugs, 3 security, 1 testing |
| P2 | 16 | 3 converter, 4 engine, 2 bugs, 1 naming, 2 standards, 2 security, 2 performance |
| P3 | 7 | 2 converter, 2 engine, 1 bug, 1 naming, 1 performance |
| **Total** | **43** | |

---

## 10. Recommendations

### Immediate (Before Production)

1. **Fix `_update_global_map()` bug** (BUG-SM-001): Change `value` to `stat_value` on `base_component.py` line 304. Better yet, remove both stale references (`{stat_name}: {value}`) and log just the three main stats. **Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

2. **Fix `GlobalMap.get()` bug** (BUG-SM-002): Add `default: Any = None` parameter to the `get()` method signature in `global_map.py` line 26. This fixes both direct calls and the two-argument call from `get_component_stat()` on line 58. **Impact**: Fixes ALL components. **Risk**: Very low.

3. **Create unit test suite** (TEST-SM-001): Implement at minimum the 7 P0 test cases listed in Section 8.2. All tests should mock `smtplib.SMTP` and `smtplib.SMTP_SSL` to avoid actual SMTP connections. Verify sendmail arguments, exception handling, and statistics tracking.

4. **Fix SMTP connection leak** (BUG-SM-004, ENG-SM-004): Wrap the SMTP connection in a `try/finally` block to ensure `server.quit()` is always called:
   ```python
   server = None
   try:
       if use_ssl:
           server = smtplib.SMTP_SSL(smtp_host, smtp_port)
       else:
           server = smtplib.SMTP(smtp_host, smtp_port)
       if use_starttls:
           server.starttls()
       if auth_username and auth_password:
           server.login(auth_username, auth_password)
       server.sendmail(from_email, all_recipients, msg.as_string())
   finally:
       if server:
           try:
               server.quit()
           except Exception:
               pass
   ```

5. **Set `{id}_ERROR_MESSAGE` in globalMap** (ENG-SM-001): In the SMTP error handler (lines 220-226) and generic error handler (lines 228-232), add `self.global_map.put(f"{self.id}_ERROR_MESSAGE", error_msg)` before the `die_on_error` check. This is the ONLY meaningful globalMap variable for tSendMail and is the primary mechanism for SMTP error reporting in Talend jobs.

### Short-Term (Hardening)

6. **Fix attachment filename** (BUG-SM-003, ENG-SM-003): Change line 181 to use `os.path.basename(attachment)`:
   ```python
   import os
   part.add_header('Content-Disposition', f'attachment; filename={os.path.basename(attachment)}')
   ```

7. **Fix generic exception handler** (BUG-SM-005): Add `die_on_error=false` handling to lines 228-232:
   ```python
   except Exception as e:
       error_msg = f"Unexpected error sending email: {str(e)}"
       logger.error(f"[{self.id}] {error_msg}")
       if die_on_error:
           raise ComponentExecutionError(self.id, error_msg, e) from e
       else:
           logger.warning(f"[{self.id}] Unexpected error but continuing due to die_on_error=False")
   ```

8. **Add null checks in converter** (CONV-SM-002): Add null checks for all `node.find()` calls in `parse_tsendmail()`. Follow the pattern from `parse_t_xml_map()`:
   ```python
   smtp_host_elem = node.find('.//elementParameter[@name="SMTP_HOST"]')
   component['config']['smtp_host'] = smtp_host_elem.get('value', '') if smtp_host_elem is not None else ''
   ```

9. **Fix `SMTP_PORT` conversion** (CONV-SM-003): Use safe conversion with fallback:
   ```python
   port_value = node.find('.//elementParameter[@name="SMTP_PORT"]').get('value', '25')
   try:
       component['config']['smtp_port'] = int(port_value)
   except (ValueError, TypeError):
       component['config']['smtp_port'] = port_value  # Let engine handle context variable
   ```

10. **Parse attachments table** (CONV-SM-001): Extract the ATTACHMENTS table parameter from Talend XML:
    ```python
    attachments = []
    attachment_nodes = node.findall('.//elementParameter[@name="ATTACHMENTS"]/elementValue')
    for att_node in attachment_nodes:
        attachments.append(att_node.get('value', ''))
    component['config']['attachments'] = attachments
    ```

11. **Extract MIME_SUBTYPE and ENCODING** (CONV-SM-005, CONV-SM-006): Add to `parse_tsendmail()`:
    ```python
    mime_elem = node.find('.//elementParameter[@name="MIME_SUBTYPE"]')
    component['config']['text_subtype'] = mime_elem.get('value', 'plain').lower() if mime_elem is not None else 'plain'
    encoding_elem = node.find('.//elementParameter[@name="ENCODING"]')
    component['config']['encoding'] = encoding_elem.get('value', 'UTF-8') if encoding_elem is not None else 'UTF-8'
    ```

12. **Remove dead `validate_config()` method** (BUG-SM-006, STD-SM-002): Delete lines 240-252. The `_validate_config()` method (lines 82-114) is the correct validation method, is properly called from `_process()`, and is more comprehensive.

13. **Fix empty CC/BCC handling** (BUG-SM-007): Filter empty strings from recipient lists:
    ```python
    cc_emails = [e for e in self.config.get('cc', []) if e.strip()]
    bcc_emails = [e for e in self.config.get('bcc', []) if e.strip()]
    ```

14. **Add SMTP timeout** (ENG-SM-007): Pass timeout parameter to SMTP connection:
    ```python
    timeout = self.config.get('smtp_timeout', 60)
    if use_ssl:
        server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=timeout)
    else:
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=timeout)
    ```

### Long-Term (Feature Parity)

15. **Add Importance header** (ENG-SM-002): Map importance config to email headers:
    ```python
    importance = self.config.get('importance', 'Normal')
    if importance != 'Normal':
        msg['Importance'] = importance
        priority_map = {'High': '1', 'Low': '5'}
        msg['X-Priority'] = priority_map.get(importance, '3')
    ```

16. **Add sender display name** (ENG-SM-005): Support `"Name" <email>` format:
    ```python
    from email.utils import formataddr
    sender_name = self.config.get('sender_name')
    if sender_name:
        msg['From'] = formataddr((sender_name, from_email))
    else:
        msg['From'] = from_email
    ```

17. **Add custom headers support** (ENG-SM-006): Iterate headers config and add to message:
    ```python
    custom_headers = self.config.get('other_headers', [])
    for header in custom_headers:
        msg[header['key']] = header['value']
    ```

18. **Add OAuth2 support** (ENG-SM-009): Implement OAuth2 XOAUTH2 SASL mechanism for Gmail and Office 365. This requires external token management.

19. **Add password encryption/masking** (SEC-SM-002): Implement a credential store or at minimum mask passwords in log output and config dumps.

20. **Create integration test** (TEST-SM-002): Build an end-to-end test exercising a subjob with error trigger -> tSendMail in the v1 engine, verifying trigger dispatch, context variable resolution, and globalMap ERROR_MESSAGE propagation.

---

## Appendix A: Converter Parameter Mapping Code

```python
# component_parser.py lines 1136-1152
def parse_tsendmail(self, node, component: Dict) -> Dict:
    """Parse tSendMail specific configuration"""
    component['config']['smtp_host'] = node.find('.//elementParameter[@name="SMTP_HOST"]').get('value', '')
    component['config']['smtp_port'] = int(node.find('.//elementParameter[@name="SMTP_PORT"]').get('value', '25'))
    component['config']['from_email'] = node.find('.//elementParameter[@name="FROM"]').get('value', '')
    component['config']['to'] = [email.strip() for email in node.find('.//elementParameter[@name="TO"]').get('value', '').split(';')]
    component['config']['cc'] = [email.strip() for email in node.find('.//elementParameter[@name="CC"]').get('value', '').split(';')]
    component['config']['bcc'] = [email.strip() for email in node.find('.//elementParameter[@name="BCC"]').get('value', '').split(';')]
    component['config']['subject'] = node.find('.//elementParameter[@name="SUBJECT"]').get('value', '')
    component['config']['message'] = node.find('.//elementParameter[@name="MESSAGE"]').get('value', '')
    component['config']['attachments'] = []
    component['config']['ssl'] = node.find('.//elementParameter[@name="SSL"]').get('value', 'false').lower() == 'true'
    component['config']['starttls'] = node.find('.//elementParameter[@name="STARTTLS"]').get('value', 'false').lower() == 'true'
    component['config']['auth_username'] = node.find('.//elementParameter[@name="AUTH_USERNAME"]').get('value', '')
    component['config']['auth_password'] = node.find('.//elementParameter[@name="AUTH_PASSWORD"]').get('value', '')
    component['config']['die_on_error'] = node.find('.//elementParameter[@name="DIE_ON_ERROR"]').get('value', 'true').lower() == 'true'
    return component
```

**Notes on this code**:
- Line 1139: `int()` cast on SMTP_PORT with no error handling. Context variables or expressions will crash.
- Line 1141-1143: Recipient split on `;` only. Comma-separated recipients not handled.
- Line 1146: `attachments = []` hardcoded. Talend ATTACHMENTS table not parsed at all.
- Line 1150: `AUTH_PASSWORD` extracted as plain text. Talend encrypts this in the repository.
- Lines 1138-1151: No `node.find()` null checks. Missing XML elements cause `AttributeError`.

---

## Appendix B: Engine Class Structure

```
SendMailComponent (BaseComponent)
    Constants:
        DEFAULT_SMTP_PORT = 25
        DEFAULT_TEXT_SUBTYPE = 'plain'
        DEFAULT_ENCODING = 'utf-8'

    Methods:
        _validate_config() -> List[str]          # ACTIVE -- called from _process() line 134
        _process(input_data) -> Dict[str, Any]   # Main entry point -- sends email
        validate_config() -> bool                # DEAD CODE -- never called, duplicates _validate_config()

    Inherited from BaseComponent:
        execute(input_data) -> Dict[str, Any]    # Main lifecycle (resolves Java/context, calls _process)
        _update_stats(rows_read, rows_ok, rows_reject)  # Statistics accumulation
        _update_global_map()                     # Pushes stats to globalMap (BUGGY -- see BUG-SM-001)
        _resolve_java_expressions()              # Resolves {{java}} markers in config
        _determine_execution_mode()              # Always HYBRID -> auto-selects BATCH for null input
        _auto_select_mode(input_data)            # Returns BATCH for None input
        _execute_batch(input_data)               # Delegates to _process()
        _execute_streaming(input_data)            # For None input, delegates to _process()
        validate_schema(df, schema)              # Not used by SendMail (no data)
        get_status() -> ComponentStatus          # Returns execution status
        get_stats() -> Dict[str, Any]            # Returns stats copy
```

---

## Appendix C: Complete Talend Parameter to V1 Config Key Reference

| Talend Parameter | V1 Config Key | Status | Priority to Add |
|------------------|---------------|--------|-----------------|
| `SMTP_HOST` | `smtp_host` | Mapped | -- |
| `SMTP_PORT` | `smtp_port` | Mapped (buggy int cast) | Fix conversion |
| `FROM` | `from_email` | Mapped | -- |
| `TO` | `to` | Mapped (semicolon split only) | Fix to also split on comma |
| `CC` | `cc` | Mapped (semicolon split only) | Fix to also split on comma |
| `BCC` | `bcc` | Mapped (semicolon split only) | Fix to also split on comma |
| `SUBJECT` | `subject` | Mapped | -- |
| `MESSAGE` | `message` | Mapped | -- |
| `SSL` | `ssl` | Mapped | -- |
| `STARTTLS` | `starttls` | Mapped | -- |
| `AUTH_USERNAME` | `auth_username` | Mapped | -- |
| `AUTH_PASSWORD` | `auth_password` | Mapped (plain text) | Add encryption |
| `DIE_ON_ERROR` | `die_on_error` | Mapped | -- |
| `ATTACHMENTS` | `attachments` | **Hardcoded `[]`** | P1 -- parse table |
| `IMPORTANCE` | `importance` | **Not Mapped** | P2 |
| `MIME_SUBTYPE` | `text_subtype` | **Not Mapped** | P2 |
| `ENCODING` | `encoding` | **Not Mapped** | P2 |
| `SHOW_SENDER_NAME` | `show_sender_name` | **Not Mapped** | P2 |
| `SENDER_NAME` | `sender_name` | **Not Mapped** | P2 |
| `OTHER_HEADERS` | `other_headers` | **Not Mapped** | P2 |
| `DIE_IF_ATTACHMENT_DOESNT_EXIST` | `die_if_attachment_doesnt_exist` | **Not Mapped** | P2 |
| `SET_LOCALHOST` | `set_localhost` | **Not Mapped** | P3 |
| `LOCALHOST_NAME` | `localhost_name` | **Not Mapped** | P3 |
| `NEED_AUTH` | `need_auth` | **Not Mapped** | P3 (implicit via username) |
| `CUSTOM_PROPERTIES` | `custom_properties` | **Not Mapped** | P3 |
| `OAUTH2_TWO_LINE` | -- | **Not Mapped** | P3 |
| `TSTATCATCHER_STATS` | -- | Not needed | -- (tStatCatcher rarely used) |
| `PROPERTY_TYPE` | -- | Not needed | -- (always Built-In) |

---

## Appendix D: _validate_config() Analysis

### Active Method: `_validate_config()` (Lines 82-114)

This method performs comprehensive validation and IS called from `_process()` (line 134):

| Check | Line | Description |
|-------|------|-------------|
| Required fields | 92-95 | Checks `smtp_host`, `from_email`, `to` are present and non-empty |
| `to` is non-empty list | 98-100 | Validates `to` is a list with at least one element |
| Port range | 103-106 | If `smtp_port` provided, validates integer between 1 and 65535 |
| Optional list types | 109-112 | Validates `cc`, `bcc`, `attachments` are lists (if present) |

**Missing validations**:
- No email format validation (e.g., `@` in addresses)
- No validation of `ssl` + `starttls` mutual exclusivity (see BUG-SM-008)
- No validation that `auth_username` and `auth_password` are both present or both absent
- No `text_subtype` validation (should be 'plain' or 'html')
- No `encoding` validation (should be a valid Python codec name)

### Dead Method: `validate_config()` (Lines 240-252)

This method performs a SUBSET of validation and is NEVER called:

| Check | Line | Description |
|-------|------|-------------|
| Required fields | 247-250 | Checks `smtp_host`, `from_email`, `to` are present and non-empty |

This method only checks 3 fields and returns `bool` instead of `List[str]`. It is strictly less useful than `_validate_config()`.

**Recommendation**: Delete `validate_config()` (lines 240-252). It is dead code that duplicates partial logic from the active `_validate_config()` method.

---

## Appendix E: _process() Execution Flow

```
_process(input_data=None)
    |
    +-- Log "Sending email started"
    |
    +-- _validate_config()
    |   |-- Check required fields (smtp_host, from_email, to)
    |   |-- Validate to is non-empty list
    |   |-- Validate smtp_port range (1-65535)
    |   |-- Validate cc, bcc, attachments are lists
    |   +-- If errors: raise ConfigurationError
    |
    +-- Extract config with defaults
    |   |-- smtp_host, smtp_port (default 25)
    |   |-- from_email, to, cc (default []), bcc (default [])
    |   |-- subject (default ''), message (default '')
    |   |-- attachments (default [])
    |   |-- auth_username, auth_password (optional)
    |   |-- use_ssl (default False), use_starttls (default False)
    |   +-- die_on_error (default True)
    |
    +-- Create MIMEMultipart message
    |   |-- Set From, To, Cc, Subject headers
    |   +-- Attach MIMEText body (text_subtype, encoding)
    |
    +-- For each attachment:
    |   |-- Open file, read binary content
    |   |-- Create MIMEBase('application', 'octet-stream')
    |   |-- Base64 encode payload
    |   |-- Set Content-Disposition with FULL PATH (BUG-SM-003)
    |   +-- On error: raise FileOperationError or skip (die_on_error)
    |
    +-- Connect to SMTP server
    |   |-- SMTP_SSL if ssl=True, else SMTP
    |   |-- STARTTLS if starttls=True
    |   +-- Login if auth_username AND auth_password
    |       (NO try/finally -- BUG-SM-004)
    |
    +-- server.sendmail(from_email, all_recipients, msg.as_string())
    +-- server.quit()
    |
    +-- On SMTPException/ConnectionError/OSError:
    |   |-- die_on_error=True: raise ComponentExecutionError
    |   +-- die_on_error=False: log warning, continue
    |
    +-- On other Exception (includes FileOperationError -- BUG-SM-009):
    |   |-- die_on_error=True: raise ComponentExecutionError
    |   +-- die_on_error=False: MISSING HANDLER (BUG-SM-005)
    |
    +-- _update_stats(0, 0, 0)   <-- reached even after silent failure (BUG-SM-010)
    +-- Log "Email sending complete"
    +-- return {}                 <-- indistinguishable from success (BUG-SM-010)
```

---

## Appendix F: Edge Case Analysis

### Edge Case 1: Empty recipient list

| Aspect | Detail |
|--------|--------|
| **Talend** | Fails with validation error -- `TO` is mandatory. |
| **V1** | `_validate_config()` checks `not isinstance(to_emails, list) or len(to_emails) == 0` (line 99). Raises `ConfigurationError`. |
| **Verdict** | CORRECT |

### Edge Case 2: NaN/None values in config

| Aspect | Detail |
|--------|--------|
| **Talend** | Not applicable -- Talend GUI prevents null values in required fields. |
| **V1** | If `smtp_host` is `None`, `self.config.get('smtp_host')` returns `None`. `_validate_config()` check `not self.config.get(field)` catches this (None is falsy). `ConfigurationError` raised. |
| **Verdict** | CORRECT for required fields. Optional fields like `subject` default to empty string, which is acceptable. |

### Edge Case 3: Empty string subject/message

| Aspect | Detail |
|--------|--------|
| **Talend** | Sends email with empty subject and/or body. No error. |
| **V1** | `subject = self.config.get('subject', '')` and `message = self.config.get('message', '')`. MIMEText created with empty body. Email sent successfully. |
| **Verdict** | CORRECT |

### Edge Case 4: SSL + STARTTLS both enabled

| Aspect | Detail |
|--------|--------|
| **Talend** | Undefined behavior. UI does not prevent enabling both. Typically, SSL takes precedence. |
| **V1** | Lines 200-207: If `use_ssl=True`, creates `SMTP_SSL`. Then if `use_starttls=True`, calls `server.starttls()` on an already-SSL connection. This will raise `ssl.SSLError` or `smtplib.SMTPNotSupportedError` because TLS is already active. See BUG-SM-008. |
| **Verdict** | BUG -- no validation to prevent this configuration. Will crash at runtime. Should either validate mutually exclusive in `_validate_config()` or skip STARTTLS when SSL is active. |

### Edge Case 5: Missing attachment file

| Aspect | Detail |
|--------|--------|
| **Talend** | With `DIE_IF_ATTACHMENT_DOESNT_EXIST=true` (default): job fails. With `false`: email sent without attachment. |
| **V1** | Lines 183-189: Catches `FileNotFoundError`. If `die_on_error=True`, raises `FileOperationError`. If `False`, logs warning and skips. |
| **Verdict** | PARTIAL -- uses `die_on_error` instead of separate `DIE_IF_ATTACHMENT_DOESNT_EXIST`. Behavior matches for default case (both true). Mismatches when die_on_error=false but die_if_attachment_doesnt_exist=true. |

### Edge Case 6: Very large attachment file

| Aspect | Detail |
|--------|--------|
| **Talend** | JavaMail handles large files. Memory depends on JVM heap. |
| **V1** | `file.read()` (line 179) loads entire file into memory. For 500MB attachment: ~500MB base + ~667MB Base64 encoded + ~667MB from `msg.as_string()` serialization (PERF-SM-003) = ~1.8GB memory. No size limit. |
| **Verdict** | GAP -- no size limit or warning for large attachments. Memory usage is 3-4x attachment size due to PERF-SM-001 and PERF-SM-003. |

### Edge Case 7: Unicode in email addresses

| Aspect | Detail |
|--------|--------|
| **Talend** | JavaMail supports internationalized email addresses (RFC 6531). |
| **V1** | Python `smtplib` supports UTF-8 email addresses when using `smtplib.SMTP_SSL` with SMTPUTF8 extension. Standard `sendmail()` does not enable SMTPUTF8 by default. |
| **Verdict** | PARTIAL -- works for ASCII addresses. Internationalized addresses may fail. |

### Edge Case 8: Context variable in password

| Aspect | Detail |
|--------|--------|
| **Talend** | `context.smtp_password` resolves to the password value at runtime. |
| **V1** | `context_manager.resolve_dict()` resolves `${context.smtp_password}` before `_process()`. Works correctly. |
| **Verdict** | CORRECT (assuming password is in context variables) |

### Edge Case 9: Java expression in message body

| Aspect | Detail |
|--------|--------|
| **Talend** | `"Job failed: " + ((String)globalMap.get("tRunJob_1_ERROR_MESSAGE"))` evaluates at runtime. |
| **V1** | Converter extracts the expression as a literal string. NOT marked with `{{java}}`. The `_resolve_java_expressions()` method only processes `{{java}}`-prefixed strings. The email body will contain the literal Java expression text. |
| **Verdict** | GAP -- Java expressions in MESSAGE are not evaluated. Common use case for error notification emails. |

### Edge Case 10: SMTP server unreachable

| Aspect | Detail |
|--------|--------|
| **Talend** | `javax.mail.MessagingException` caught. ERROR_MESSAGE set in globalMap. Job fails or continues based on `DIE_ON_ERROR`. |
| **V1** | `ConnectionError` or `OSError` caught (line 220). If `die_on_error=True`, raises `ComponentExecutionError`. If `False`, logs warning. ERROR_MESSAGE NOT set in globalMap (ENG-SM-001). |
| **Verdict** | PARTIAL -- exception handling correct, but missing globalMap ERROR_MESSAGE. |

### Edge Case 11: Empty DataFrame passed as input_data

| Aspect | Detail |
|--------|--------|
| **Talend** | Not applicable -- tSendMail has no input row connections. |
| **V1** | `_process(input_data=None)` ignores `input_data` entirely. If a DataFrame is somehow passed, it is still ignored. No error. |
| **Verdict** | CORRECT -- gracefully ignores unexpected input. |

### Edge Case 12: Special characters in subject line

| Aspect | Detail |
|--------|--------|
| **Talend** | JavaMail handles RFC 2047 encoding for non-ASCII characters in headers. |
| **V1** | Python `email.mime.multipart` handles non-ASCII in `Subject` header via RFC 2047 encoding when the MIMEText charset is set. Works with UTF-8 default. |
| **Verdict** | CORRECT |

### Edge Case 13: Concurrent email sends (thread safety)

| Aspect | Detail |
|--------|--------|
| **Talend** | Each component instance is single-threaded within its subjob. |
| **V1** | Each `SendMailComponent` instance creates its own SMTP connection in `_process()`. No shared state between instances. Different instances can safely send concurrently. Same instance should NOT be reused concurrently (stats are mutable). |
| **Verdict** | CORRECT for separate instances. Not safe for same-instance reuse. |

### Edge Case 14: Password with special characters

| Aspect | Detail |
|--------|--------|
| **Talend** | Encrypted in repository. Decrypted at runtime. |
| **V1** | Plain text in config. Passed directly to `server.login()`. Special characters (quotes, backslashes) work fine since Python string handling is robust. |
| **Verdict** | CORRECT functionally. INSECURE for storage. |

### Edge Case 15: SMTP server requires specific TLS version

| Aspect | Detail |
|--------|--------|
| **Talend** | Configurable via `CUSTOM_PROPERTIES` (`mail.smtp.ssl.protocols`). |
| **V1** | Python's `ssl` module uses system default TLS version. No configuration option. May fail with servers requiring TLS 1.2+ if Python defaults to TLS 1.0. |
| **Verdict** | GAP -- no TLS version configuration. |

---

## Appendix G: Cross-Cutting Issues

The following issues were discovered during this audit but affect the entire v1 engine, not just `SendMailComponent`:

| ID | Priority | Component | Issue |
|----|----------|-----------|-------|
| BUG-SM-001 | **P0** | `base_component.py:304` | `_update_global_map()` references undefined `value` variable. Will crash ALL components. |
| BUG-SM-002 | **P0** | `global_map.py:28` | `GlobalMap.get()` references undefined `default` parameter. Will crash on any `get()` call. |

These should be tracked in a cross-cutting issues report as well.

---

## Appendix H: Implementation Fix Guides

### Fix Guide: BUG-SM-001 -- `_update_global_map()` undefined variable

**File**: `src/v1/engine/base_component.py`
**Line**: 304

**Current code (broken)**:
```python
logger.info(f"Component {self.id}: Updated stats - NB_LINE:{self.stats['NB_LINE']} NB_LINE_OK:{self.stats['NB_LINE_OK']} NB_LINE_REJECT:{self.stats['NB_LINE_REJECT']} {stat_name}: {value}")
```

**Fix**:
```python
logger.info(f"Component {self.id}: Updated stats - NB_LINE:{self.stats['NB_LINE']} NB_LINE_OK:{self.stats['NB_LINE_OK']} NB_LINE_REJECT:{self.stats['NB_LINE_REJECT']}")
```

**Explanation**: `{value}` references an undefined variable (the loop variable is `stat_value`). The `{stat_name}` reference would show only the last loop iteration value, which is misleading. Best fix is to remove both stale references.

**Impact**: Fixes ALL components (cross-cutting). **Risk**: Very low (log message only).

---

### Fix Guide: BUG-SM-002 -- `GlobalMap.get()` undefined default

**File**: `src/v1/engine/global_map.py`
**Line**: 26-28

**Current code (broken)**:
```python
def get(self, key: str) -> Optional[Any]:
    """Retrieve a value from the global map"""
    return self._map.get(key, default)
```

**Fix**:
```python
def get(self, key: str, default: Any = None) -> Optional[Any]:
    """Retrieve a value from the global map"""
    return self._map.get(key, default)
```

**Impact**: Fixes ALL components and any code calling `global_map.get()`. **Risk**: Very low (adds optional parameter with backward-compatible default).

---

### Fix Guide: BUG-SM-004 -- SMTP connection leak

**File**: `src/v1/engine/components/control/send_mail.py`
**Lines**: 198-216

**Current code (broken)**:
```python
if use_ssl:
    server = smtplib.SMTP_SSL(smtp_host, smtp_port)
else:
    server = smtplib.SMTP(smtp_host, smtp_port)

if use_starttls:
    server.starttls()

if auth_username and auth_password:
    server.login(auth_username, auth_password)

all_recipients = to_emails + cc_emails + bcc_emails
server.sendmail(from_email, all_recipients, msg.as_string())
server.quit()
```

**Fix**:
```python
server = None
try:
    if use_ssl:
        server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=60)
    else:
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=60)

    if use_starttls and not use_ssl:
        server.starttls()

    if auth_username and auth_password:
        server.login(auth_username, auth_password)

    all_recipients = to_emails + cc_emails + bcc_emails
    server.sendmail(from_email, all_recipients, msg.as_string())
finally:
    if server:
        try:
            server.quit()
        except Exception:
            pass
```

**Explanation**: Wraps SMTP connection in `try/finally` to ensure `server.quit()` is always called. Also adds `timeout=60` and prevents STARTTLS on already-SSL connections.

**Impact**: Fixes connection leak. **Risk**: Low (only changes cleanup behavior).

---

### Fix Guide: BUG-SM-003 -- Attachment filename path leak

**File**: `src/v1/engine/components/control/send_mail.py`
**Line**: 181

**Current code (broken)**:
```python
part.add_header('Content-Disposition', f'attachment; filename={attachment}')
```

**Fix**:
```python
import os
part.add_header('Content-Disposition', f'attachment; filename={os.path.basename(attachment)}')
```

**Explanation**: Uses `os.path.basename()` to extract just the filename, preventing full server path from appearing in the email attachment.

**Impact**: Fixes path leak. **Risk**: Very low.

---

### Fix Guide: ENG-SM-001 -- Missing ERROR_MESSAGE in globalMap

**File**: `src/v1/engine/components/control/send_mail.py`
**Lines**: 220-232

**Add after each error handler** (both SMTP and generic exception blocks):
```python
if self.global_map:
    self.global_map.put(f"{self.id}_ERROR_MESSAGE", error_msg)
```

**Explanation**: Stores the error message in globalMap for downstream components, matching Talend behavior where `((String)globalMap.get("tSendMail_1_ERROR_MESSAGE"))` is used in error flows.

**Impact**: Enables SMTP error reporting in downstream components. **Risk**: Very low.

---

### Fix Guide: BUG-SM-005 -- Missing die_on_error=false handler for generic exceptions

**File**: `src/v1/engine/components/control/send_mail.py`
**Lines**: 228-232

**Current code (incomplete)**:
```python
except Exception as e:
    error_msg = f"Unexpected error sending email: {str(e)}"
    logger.error(f"[{self.id}] {error_msg}")
    if die_on_error:
        raise ComponentExecutionError(self.id, error_msg, e) from e
```

**Fix**:
```python
except Exception as e:
    error_msg = f"Unexpected error sending email: {str(e)}"
    logger.error(f"[{self.id}] {error_msg}")
    if self.global_map:
        self.global_map.put(f"{self.id}_ERROR_MESSAGE", error_msg)
    if die_on_error:
        raise ComponentExecutionError(self.id, error_msg, e) from e
    else:
        logger.warning(f"[{self.id}] Unexpected error but continuing due to die_on_error=False")
```

**Impact**: Ensures all exceptions respect the `die_on_error` flag. **Risk**: Very low.

---

## Appendix I: Converter Dispatch Chain

```
converter.py:_parse_component(node)
    |
    +-- Extract component_type from XML (e.g., 'tSendMail')
    |
    +-- Build base component dict:
    |   {
    |     'id': unique_name,
    |     'type': mapped_component_type,  # 'SendMailComponent' (from COMPONENT_TYPE_MAP)
    |     'config': {},
    |     'connections': [],
    |     'schema': {}
    |   }
    |
    +-- elif component_type == 'tSendMail':  (line 264)
    |   +-- self.component_parser.parse_tsendmail(node, component)
    |       |
    |       +-- XPath extraction of 13 parameters (lines 1138-1151)
    |       +-- Hardcoded attachments = [] (line 1146)
    |       +-- Boolean conversion for ssl, starttls, die_on_error
    |       +-- int() cast for smtp_port (NO error handling)
    |       +-- Semicolon split for to, cc, bcc
    |       |
    |       +-- Returns component dict with populated config
    |
    +-- Return component to converter pipeline
```

**Component Type Mapping** (component_parser.py line 88):
```python
'tSendMail': 'SendMailComponent'
```

**Engine Registry** (engine.py lines 179-180):
```python
'SendMailComponent': SendMailComponent,
'tSendMail': SendMailComponent,
```

---

## Appendix J: Security Considerations for Production Deployment

### Password Handling

| Concern | Current State | Recommendation |
|---------|---------------|----------------|
| Password in converter output | Plain text in v1 JSON config | Use context variables: `${context.smtp_password}` |
| Password in logs | Not directly logged, but Java expression resolver may log it | Add password field to log masking list |
| Password in memory | Plain string in Python process memory | No mitigation possible in Python |
| Password in transit | Encrypted IF SSL/TLS enabled | Ensure SSL or STARTTLS is always enabled |

### Attachment Security

| Concern | Current State | Recommendation |
|---------|---------------|----------------|
| Path traversal | No sanitization | Validate against allowed base directory |
| File size | No limit | Add configurable max attachment size |
| File type | No restriction | Optional whitelist of allowed extensions |
| Path in filename | Full path leaked | Use `os.path.basename()` (see BUG-SM-003 fix) |

### SMTP Connection Security

| Concern | Current State | Recommendation |
|---------|---------------|----------------|
| Encryption | SSL and STARTTLS supported | Warn if neither SSL nor STARTTLS enabled |
| TLS version | Python default | Allow TLS version configuration |
| Certificate verification | Python default (strict) | Document any need for custom CA certificates |
| Connection timeout | No timeout | Add configurable timeout (default 60s) |

---

## Appendix K: Comparison with Talend tSendMail Code Generation

### Talend-Generated Java Code Pattern

Talend generates Java code using the JavaMail API. The typical pattern is:

```java
// Properties
Properties props = new Properties();
props.put("mail.smtp.host", smtp_host);
props.put("mail.smtp.port", smtp_port);
props.put("mail.smtp.auth", needAuth);
props.put("mail.smtp.starttls.enable", useStartTLS);
props.put("mail.smtp.ssl.enable", useSSL);
// Custom properties from CUSTOM_PROPERTIES table
for (Map.Entry<String, String> entry : customProps.entrySet()) {
    props.put(entry.getKey(), entry.getValue());
}

// Session
Session session = Session.getInstance(props, authenticator);

// Message
MimeMessage msg = new MimeMessage(session);
msg.setFrom(new InternetAddress(from, senderName));
msg.setRecipients(Message.RecipientType.TO, InternetAddress.parse(to));
msg.setRecipients(Message.RecipientType.CC, InternetAddress.parse(cc));
msg.setRecipients(Message.RecipientType.BCC, InternetAddress.parse(bcc));
msg.setSubject(subject, encoding);

// Importance
if (!"Normal".equals(importance)) {
    msg.setHeader("Importance", importance);
    msg.setHeader("X-Priority", priorityMap.get(importance));
}

// Body
MimeBodyPart textPart = new MimeBodyPart();
textPart.setText(message, encoding, mimeSubtype);

// Attachments
MimeMultipart multipart = new MimeMultipart();
multipart.addBodyPart(textPart);
for (String[] attachment : attachments) {
    MimeBodyPart filePart = new MimeBodyPart();
    filePart.attachFile(new File(attachment[0]));
    filePart.setHeader("Content-Transfer-Encoding", attachment[1]);
    multipart.addBodyPart(filePart);
}

msg.setContent(multipart);

// Send
Transport.send(msg);

// GlobalMap
globalMap.put(componentId + "_ERROR_MESSAGE", "");
```

### Key Differences from V1 Python Implementation

| Feature | Talend Java | V1 Python | Gap? |
|---------|-------------|-----------|------|
| Mail library | JavaMail (javax.mail) | Python smtplib + email.mime | No -- equivalent |
| Session properties | Full Properties object | No equivalent | Yes -- no custom properties |
| InternetAddress parsing | `InternetAddress.parse()` | Manual split on `;` | Yes -- less robust |
| Sender name | `InternetAddress(email, name)` | Not supported | Yes |
| Importance headers | `msg.setHeader("Importance", ...)` | Not implemented | Yes |
| Attachment encoding | Per-file `Content-Transfer-Encoding` | All Base64 | Yes |
| Error message | `globalMap.put(..._ERROR_MESSAGE)` | Not implemented | Yes |
| Connection management | Transport.send() (auto-manages) | Manual connect/quit (leak risk) | Yes |
| Custom headers | Loop over OTHER_HEADERS | Not implemented | Yes |

---

## Appendix L: Detailed Engine Code Walkthrough

### Import Analysis (Lines 1-20)

```python
import logging
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

from ...base_component import BaseComponent
from ...exceptions import ComponentExecutionError, ConfigurationError, FileOperationError
```

**Assessment**:
- All imports are from Python standard library (`smtplib`, `email`) or internal project modules. No external dependencies required.
- `FileOperationError` is imported and used for attachment file errors. This is semantically correct -- attachment handling IS a file operation.
- `ComponentExecutionError` is imported for SMTP send failures. Constructor requires `(component_id, message, cause)` -- matches usage at lines 224 and 232.
- Missing import: `os` -- needed for the `os.path.basename()` fix recommended in BUG-SM-003.
- Missing import: `email.utils.formataddr` -- needed for sender display name support.

### Class Constants (Lines 77-80)

```python
DEFAULT_SMTP_PORT = 25
DEFAULT_TEXT_SUBTYPE = 'plain'
DEFAULT_ENCODING = 'utf-8'
```

**Assessment**:
- `DEFAULT_SMTP_PORT = 25`: Matches Talend default. Port 25 is standard SMTP. However, most modern SMTP servers use 587 (STARTTLS) or 465 (SSL). Using 25 as default is technically correct but may cause connection failures with servers that have disabled port 25.
- `DEFAULT_TEXT_SUBTYPE = 'plain'`: Matches Talend default. HTML requires explicit configuration.
- `DEFAULT_ENCODING = 'utf-8'`: Matches Talend default for email encoding. Note: this is DIFFERENT from the file encoding issue in tFileInputDelimited where Talend defaults to ISO-8859-15. For email, Talend defaults to UTF-8.

### _validate_config() Method (Lines 82-114)

This method is properly called from `_process()` line 134. It returns a `List[str]` of error messages.

**Validation checks performed**:

| Line | Check | Assessment |
|------|-------|------------|
| 92-95 | Required fields: `smtp_host`, `from_email`, `to` | CORRECT. Uses `not self.config.get(field)` which catches None, empty string, and missing key. |
| 98-100 | `to` must be non-empty list | CORRECT. Validates both type (list) and non-emptiness. |
| 103-106 | `smtp_port` range 1-65535 | CORRECT. Only validates if port is provided (not None). Validates type (int) and range. |
| 109-112 | `cc`, `bcc`, `attachments` must be lists if present | CORRECT. Allows None (missing) but rejects non-list values. |

**Validation checks MISSING**:

| Missing Check | Risk | Priority |
|---------------|------|----------|
| Email format validation (@ in addresses) | Invalid emails cause SMTP rejection at send time | P2 |
| SSL + STARTTLS mutual exclusivity | Causes `ssl.SSLError` at runtime | P2 |
| Auth credentials paired (both present or both absent) | Auth with only username or only password fails at SMTP login | P2 |
| `text_subtype` value validation ('plain' or 'html') | Invalid subtype creates malformed email | P3 |
| `encoding` codec validation | Invalid encoding raises `LookupError` at MIMEText creation | P3 |
| Attachment file existence (pre-check) | Discovered at send time, not validation time | P3 |

### _process() Method Detailed Analysis (Lines 116-238)

**Line 131**: `logger.info(f"[{self.id}] Sending email started")`
- Correct INFO-level start marker.

**Lines 133-138**: Configuration validation
- Calls `_validate_config()` and raises `ConfigurationError` with joined error messages.
- This is the CORRECT pattern per STANDARDS.md -- `_validate_config()` is called and its results are acted upon.
- Unlike many other components (e.g., FileInputDelimited where `_validate_config()` is dead code), SendMailComponent properly invokes validation.

**Lines 141-155**: Config extraction with defaults
- All config values extracted via `self.config.get()` with sensible defaults.
- `die_on_error` defaults to `True` (line 155), matching Talend default.
- `smtp_port` defaults to `self.DEFAULT_SMTP_PORT` (25) -- correct.
- Note: `text_subtype` and `encoding` are extracted from config (lines 168-169) but NOT listed in `_validate_config()`.

**Lines 157-171**: Email message construction
- Creates `MIMEMultipart()` container -- correct for emails with attachments.
- Sets `From`, `To`, `Cc`, `Subject` headers.
- **Missing**: `Bcc` is NOT set in headers (correct -- BCC should not appear in headers).
- **Missing**: `Importance`, `X-Priority`, custom headers.
- `MIMEText(message, subtype, encoding)` correctly creates the body part.

**Lines 173-196**: Attachment handling
- Iterates `attachments` list (empty by default due to converter bug CONV-SM-001).
- Opens file in binary mode (`'rb'`) -- correct for all file types.
- Creates `MIMEBase('application', 'octet-stream')` -- generic binary type. This is acceptable for most attachments but loses MIME type specificity (e.g., `application/pdf` for PDF files).
- `encoders.encode_base64(part)` -- always Base64. No option for 7bit, 8bit, quoted-printable.
- `Content-Disposition` header uses full path (BUG-SM-003).
- Error handling: `FileNotFoundError` specific catch, then generic `Exception` catch. Both respect `die_on_error`.

**Lines 198-216**: SMTP connection and send
- SSL vs plain connection selection is correct.
- STARTTLS called after plain connection -- correct sequence.
- Auth only if BOTH username AND password present -- correct.
- `server.sendmail(from_email, all_recipients, msg.as_string())` -- correct API usage.
- **CRITICAL**: No `try/finally` around connection. If any line between connect and quit raises, connection is leaked (BUG-SM-004).

**Lines 220-232**: Exception handling
- First block catches SMTP-specific exceptions (`SMTPException`, `ConnectionError`, `OSError`) -- good specificity.
- Second block catches generic `Exception` -- acceptable as catch-all.
- Both blocks log error and check `die_on_error`.
- **BUG-SM-005**: Second block missing `else` branch for `die_on_error=False`.

**Lines 234-238**: Stats update and return
- `_update_stats(0, 0, 0)` -- always zero. Correct for non-data component.
- Returns `{}` -- empty dict. Base class `_execute_batch()` returns this directly.

### validate_config() Method Analysis (Lines 240-252) -- DEAD CODE

This public method is NEVER called by any code path:
- Not called from `__init__()` (base class does not call validation)
- Not called from `execute()` (base class does not call it)
- Not called from `_process()` (uses `_validate_config()` instead)
- Not called from any external code (engine does not call it)

The method duplicates a SUBSET of `_validate_config()` logic:
- Checks same 3 required fields (`smtp_host`, `from_email`, `to`)
- Returns `bool` instead of `List[str]` (less informative)
- Missing: port range validation, list type validation

**Recommendation**: Delete this method entirely. It serves no purpose and creates confusion about which validation method is canonical.

---

## Appendix M: Email Protocol Reference

### SMTP Connection Modes

| Mode | Port | Encryption | Python API | Talend Config |
|------|------|------------|-----------|---------------|
| Plain SMTP | 25 | None | `smtplib.SMTP()` | `SSL=false`, `STARTTLS=false` |
| STARTTLS | 587 | Upgrade to TLS | `smtplib.SMTP()` + `.starttls()` | `SSL=false`, `STARTTLS=true` |
| SMTPS (Implicit TLS) | 465 | Full TLS from start | `smtplib.SMTP_SSL()` | `SSL=true`, `STARTTLS=false` |
| SSL + STARTTLS (invalid) | -- | Undefined | Crash | `SSL=true`, `STARTTLS=true` |

### Common SMTP Server Configurations

| Provider | Host | Port | Mode | Auth |
|----------|------|------|------|------|
| Gmail | smtp.gmail.com | 465 | SSL | OAuth2 or App Password |
| Gmail | smtp.gmail.com | 587 | STARTTLS | OAuth2 or App Password |
| Office 365 | smtp.office365.com | 587 | STARTTLS | OAuth2 or Basic |
| Amazon SES | email-smtp.us-east-1.amazonaws.com | 587 | STARTTLS | Basic (IAM credentials) |
| SendGrid | smtp.sendgrid.net | 587 | STARTTLS | Basic (API key) |

### Email Header Standards

| Header | RFC | Description | V1 Support |
|--------|-----|-------------|------------|
| `From` | 5322 | Sender address | Yes (bare address only) |
| `To` | 5322 | Primary recipients | Yes |
| `Cc` | 5322 | Carbon copy recipients | Yes |
| `Bcc` | 5322 | Blind carbon copy | Yes (not in headers) |
| `Subject` | 5322 | Message subject | Yes |
| `Content-Type` | 2045 | MIME type of body | Yes (text/plain or text/html) |
| `Content-Transfer-Encoding` | 2045 | Encoding of body | Yes (via MIMEText) |
| `Importance` | 2156 | Message priority | **No** |
| `X-Priority` | Non-standard | Priority (1-5 scale) | **No** |
| `Reply-To` | 5322 | Reply address | **No** (requires custom headers) |
| `MIME-Version` | 2045 | MIME version | Yes (auto-set by MIMEMultipart) |

---

## Appendix N: Runtime Scenario Analysis

### Scenario 1: Normal Email Send (Happy Path)

```
Input: smtp_host="smtp.company.com", smtp_port=587, starttls=True,
       from_email="noreply@company.com", to=["admin@company.com"],
       subject="Job Complete", message="ETL job finished.", die_on_error=True

Execution Flow:
1. execute() -> _resolve_java_expressions() (no markers found)
2. execute() -> context_manager.resolve_dict() (resolves ${context.*})
3. execute() -> _auto_select_mode(None) -> BATCH
4. execute() -> _execute_batch(None) -> _process(None)
5. _process() -> _validate_config() -> [] (no errors)
6. _process() -> Build MIMEMultipart with From/To/Subject/Body
7. _process() -> smtplib.SMTP("smtp.company.com", 587)
8. _process() -> server.starttls()
9. _process() -> server.sendmail(...)
10. _process() -> server.quit()
11. _process() -> _update_stats(0, 0, 0)
12. _process() -> return {}
13. execute() -> _update_global_map() -> CRASH on BUG-SM-001 (if global_map set)
14. execute() -> status = SUCCESS (if no global_map)
15. execute() -> return {'stats': {NB_LINE: 0, ...}}

Result: Email sent successfully. Stats all zero. Global map may crash.
```

### Scenario 2: SMTP Server Unreachable + die_on_error=False

```
Input: smtp_host="bad.server.com", smtp_port=25, die_on_error=False

Execution Flow:
1-5. Same as Scenario 1
6. _process() -> Build MIMEMultipart
7. _process() -> smtplib.SMTP("bad.server.com", 25) -> raises ConnectionError
8. Exception caught (line 220)
9. logger.error("Failed to send email: [Errno 111] Connection refused")
10. die_on_error=False -> logger.warning("...continuing...")
11. ERROR_MESSAGE NOT stored in globalMap (ENG-SM-001)
12. _process() -> _update_stats(0, 0, 0)
13. _process() -> return {}
14. execute() -> _update_global_map() -> CRASH on BUG-SM-001 (if global_map set)

Result: Email not sent. Warning logged. Job continues. Error details LOST
        (not in globalMap for downstream reference).
```

### Scenario 3: Missing Attachment + die_on_error=True

```
Input: attachments=["/nonexistent/file.pdf"], die_on_error=True

Execution Flow:
1-6. Same as Scenario 1
7. _process() -> Iterate attachments
8. open("/nonexistent/file.pdf", 'rb') -> raises FileNotFoundError
9. Exception caught (line 183)
10. die_on_error=True -> raise FileOperationError("Attachment file not found")
11. Propagates to execute() except block (line 227)
12. execute() -> status = ERROR, error_message = "Attachment file not found"
13. execute() -> _update_global_map() -> CRASH on BUG-SM-001 (if global_map set)
14. execute() -> re-raise FileOperationError

Result: Job fails with FileOperationError. Email NOT sent.
        SMTP connection never opened (error before connect).
```

### Scenario 4: Auth Failure + die_on_error=True

```
Input: auth_username="user", auth_password="wrong", die_on_error=True

Execution Flow:
1-8. Same as Scenario 1 (through starttls)
9. server.login("user", "wrong") -> raises SMTPAuthenticationError
10. server.quit() NOT called (BUG-SM-004 -- no finally block)
11. Exception caught (line 220 -- SMTPAuthenticationError is subclass of SMTPException)
12. die_on_error=True -> raise ComponentExecutionError
13. execute() -> status = ERROR
14. execute() -> _update_global_map() -> CRASH on BUG-SM-001

Result: Job fails. SMTP connection LEAKED (not closed).
        Connection remains open until garbage collected or timeout.
```

---

## Appendix O: Regression Risk Assessment

### Changes Required and Their Risk Profile

| Fix | Files Modified | Risk Level | Testing Required | Cross-Cutting? |
|-----|---------------|------------|------------------|----------------|
| BUG-SM-001: _update_global_map() | base_component.py | Very Low | All component tests | Yes -- ALL components |
| BUG-SM-002: GlobalMap.get() | global_map.py | Very Low | GlobalMap unit tests | Yes -- ALL components |
| BUG-SM-003: Attachment basename | send_mail.py | Very Low | Attachment test | No |
| BUG-SM-004: SMTP try/finally | send_mail.py | Low | SMTP error tests | No |
| BUG-SM-005: Generic exception handler | send_mail.py | Very Low | Error handling tests | No |
| BUG-SM-006: Remove dead validate_config() | send_mail.py | Very Low | None (dead code removal) | No |
| BUG-SM-007: Empty CC/BCC filter | send_mail.py | Low | CC/BCC tests | No |
| ENG-SM-001: ERROR_MESSAGE in globalMap | send_mail.py | Low | GlobalMap integration test | No |
| CONV-SM-001: Parse attachments table | component_parser.py | Medium | Converter unit tests | No |
| CONV-SM-002: Null checks in converter | component_parser.py | Low | Converter edge case tests | No |
| CONV-SM-003: Safe port conversion | component_parser.py | Low | Converter tests | No |

### Deployment Checklist

- [ ] Fix BUG-SM-001 and BUG-SM-002 FIRST (cross-cutting, blocks all components)
- [ ] Run full v1 test suite after cross-cutting fixes
- [ ] Fix BUG-SM-003 through BUG-SM-007 (component-specific)
- [ ] Add P0 unit tests (7 test cases from Section 8.2)
- [ ] Fix ENG-SM-001 (ERROR_MESSAGE in globalMap)
- [ ] Fix converter issues (CONV-SM-001 through CONV-SM-003)
- [ ] Add P1 unit tests (13 additional test cases)
- [ ] Integration test with error trigger chain
- [ ] Security review of password handling in config files
- [ ] Performance test with large attachments (>100MB)
