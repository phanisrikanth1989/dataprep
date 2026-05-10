---
phase: 14
plan: 03
slug: engine-control
type: execute
wave: 1
depends_on: [14-01]
files_modified:
  - tests/v1/engine/components/control/test_send_mail.py
  - src/v1/engine/components/control/send_mail.py  # only if BUG surfaces
autonomous: true
requirements: [TEST-11]
must_haves:
  truths:
    - "src/v1/engine/components/control/send_mail.py reports >= 95% line coverage"
    - "Existing send_mail tests still pass"
    - "smtplib.SMTP and smtplib.SMTP_SSL are boundary-mocked (D-A4); no live SMTP"
    - "All raises assertions use ETLError subclasses (FileOperationError, ConfigurationError, ComponentExecutionError), never bare Exception"
  artifacts:
    - path: tests/v1/engine/components/control/test_send_mail.py
      provides: extended coverage for SSL/STARTTLS branches, attachment exceptions, die_on_error=False warning paths, catch-all Exception
  key_links:
    - from: tests/v1/engine/components/control/test_send_mail.py
      to: src/v1/engine/components/control/send_mail.py
      via: unittest.mock.patch on smtplib.SMTP and smtplib.SMTP_SSL
---

<objective>
Lift `src/v1/engine/components/control/send_mail.py` from 60% (123 stmts, 49 missed) to >= 95%. The 49 missed lines cluster in: SSL branch (lines ~227-230), STARTTLS branch (~232-234), attachment exception paths (~210-223), `die_on_error=False` warning paths (~250-253), and the catch-all `Exception` branch (~255-260) per RESEARCH §Pattern 3. Use `unittest.mock.patch` on `smtplib.SMTP` and `smtplib.SMTP_SSL` per D-A4 -- no live SMTP, no aiosmtpd. Pattern is already established at `tests/v1/engine/components/control/test_send_mail.py:111`.
</objective>

<scope>
- MODIFIED: `tests/v1/engine/components/control/test_send_mail.py` -- add tests covering:
    1. SSL branch: `smtp_port=465`, `use_ssl=True` -> `smtplib.SMTP_SSL` instantiated, login + sendmail + quit
    2. STARTTLS branch: `starttls=True` + `auth_username`/`auth_password` -> SMTP -> starttls -> login -> sendmail -> quit
    3. Plain SMTP no auth: `smtp_port=25`, no auth -> sendmail directly
    4. Attachment success: pass a real `tmp_path / "att.txt"` via `attachments` config -> verify MIME multipart message structure
    5. Attachment missing file: `attachments=[str(tmp_path / "missing.txt")]`, `die_on_error=True` -> `FileOperationError` raised; `die_on_error=False` -> warning logged + execute proceeds
    6. SMTP send failure: `mock_server.sendmail.side_effect = smtplib.SMTPException("...")`, `die_on_error=True` -> `ComponentExecutionError`; `die_on_error=False` -> warning logged
    7. Catch-all `Exception` branch: simulate via `mock_server.sendmail.side_effect = OSError("...")` (or whatever the catch-all rewraps); assert wraps to `ComponentExecutionError`
    8. ASCII-only log messages: assert via `assert_ascii_logs` fixture from Plan 14-01
    9. Recipient handling: `to`, `cc`, `bcc` strings (semicolon- or comma-separated); empty `to` raises `ConfigurationError`
- POSSIBLY MODIFIED: `src/v1/engine/components/control/send_mail.py` -- only if a real bug surfaces. No defensive shims.
</scope>

<out_of_scope>
- aiosmtpd in-process SMTP server (CONTEXT.md Deferred Ideas).
- `die.py`, `warn.py`, `sleep.py` (already at 95%+).
- Pipeline tests for send_mail (D-C1: pure-component-with-mocked-boundary = unit-test only).
</out_of_scope>

<canonical_refs>
- `.planning/phases/14-coverage-push-to-95-per-module-floor/14-RESEARCH.md` §Pattern 3 (smtplib boundary mock), §Module Triage `send_mail.py`
- `.planning/phases/14-coverage-push-to-95-per-module-floor/14-CONTEXT.md` D-A4 (smtplib boundary mocking)
- `src/v1/engine/components/control/send_mail.py` (lift target)
- `src/v1/engine/exceptions.py` (FileOperationError, ConfigurationError, ComponentExecutionError)
- `tests/v1/engine/components/control/test_send_mail.py:111` (existing mock-pattern reference)
</canonical_refs>

<waves>

## Wave 1 -- Test extensions

### Task 14-03-001 -- Inventory missed lines and add SSL/STARTTLS branch tests

- **Type:** test
- **Description:**
    1. Run `python -m pytest tests/v1/engine/components/control/test_send_mail.py --cov=src/v1/engine/components/control/send_mail --cov-report=term-missing -q` to identify missed lines.
    2. Add tests for SSL branch (`smtplib.SMTP_SSL` patched), STARTTLS branch (`smtplib.SMTP` patched, `.starttls()` asserted), plain SMTP no-auth.
    3. Use the existing `_make_component(config)` helper from this file's head; do not introduce a new factory.
- **Files to create or modify:** `tests/v1/engine/components/control/test_send_mail.py`
- **Verification command:** `python -m pytest tests/v1/engine/components/control/test_send_mail.py -q`
- **Expected outcome:** New tests green; intermediate coverage progress visible.

### Task 14-03-002 -- Add attachment + die_on_error + catch-all branch tests

- **Type:** test
- **Description:** Add attachment success (real `tmp_path` file), attachment missing (both `die_on_error` modes), `mock_server.sendmail.side_effect` for SMTP and OSError, recipient parsing edge cases. Use `assert_ascii_logs` fixture from Plan 14-01 to verify no unicode in log output.
- **Files to create or modify:** `tests/v1/engine/components/control/test_send_mail.py`
- **Verification command:** `python -m pytest tests/v1/engine/components/control/test_send_mail.py --cov=src/v1/engine/components/control/send_mail --cov-report=term-missing -q`
- **Expected outcome:** Coverage >= 95% for `send_mail.py`; all tests green.
- **Notes:** If the catch-all `Exception` branch can never be reached (real-world unreachable), apply D-C5 -- prefer deletion of the catch-all over `# pragma: no cover`. Document outcome in plan summary.

### Task 14-03-003 -- Per-module gate verification

- **Type:** infra (verify)
- **Description:** Run gate scoped to control subsystem.
    ```bash
    rm -f .coverage* && python -m pytest tests/v1/engine/components/control/ -n auto \
      --cov=src/v1/engine/components/control --cov-report=json:cov_14_03.json -q
    python scripts/check_per_module_coverage.py cov_14_03.json --floor 95
    ```
- **Files to create or modify:** none persisted.
- **Verification command:** above.
- **Expected outcome:** Exit 0; PASS line printed.

</waves>

<verification_gate>

Plan 14-03 is GREEN when:
1. `send_mail.py` >= 95% line coverage.
2. All tests in `test_send_mail.py` pass; ASCII-log fixture clean.
3. No new pragma outside D-C3 allowlist.
4. All `pytest.raises` use specific ETLError subclasses.
5. Per-module gate exits 0 for `src/v1/engine/components/control/`.

</verification_gate>

<commit_map>

| # | Subject | Files |
|---|---------|-------|
| 1 | `test(14-03): COV-CTL-001 send_mail SSL/STARTTLS/plain branches via smtplib boundary mock` | `tests/v1/engine/components/control/test_send_mail.py` |
| 2 | `test(14-03): COV-CTL-002 send_mail attachment + die_on_error + catch-all branches` | `tests/v1/engine/components/control/test_send_mail.py` |
| 3 (conditional) | `fix(14-03): BUG-MAIL-NN <description>` -- only if bug surfaces | `src/v1/engine/components/control/send_mail.py` |

(Total: 2-3 commits.)

</commit_map>
