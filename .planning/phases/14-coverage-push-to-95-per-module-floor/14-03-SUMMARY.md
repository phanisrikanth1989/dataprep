---
phase: 14
plan: 03
slug: engine-control
subsystem: engine.components.control
tags: [coverage-lift, smtplib-boundary-mock, send-mail, attachment-handling, etlerror-rebroadcast]
status: complete
completed: 2026-05-10
duration_minutes: ~30
tasks_total: 3
tasks_completed: 3
commits_total: 3
requires:
  - "14-01 (root tests/conftest.py: assert_ascii_logs fixture)"
  - "Phase 13 baseline: src/v1/engine/components/control/send_mail.py 60% (49 missed)"
provides:
  - "src/v1/engine/components/control/send_mail.py at 100% line coverage (125 stmts, 0 missed)"
  - "ETLError-untouched re-raise pattern between attachment-loop boundary and SMTP-failure catch blocks"
affects:
  - "src/v1/engine/components/control/send_mail.py: attachment FileOperationError now surfaces with documented type when die_on_error=True"
tech_stack_added: []
tech_stack_patterns:
  - "smtplib boundary mock pattern (CONTEXT.md D-A4): patch src.v1.engine.components.control.send_mail.smtplib.{SMTP,SMTP_SSL} at the module path; assert call_args ordering of starttls/login/sendmail/quit"
  - "ETLError-rebroadcast guard pattern: insert ``except ETLError: raise`` between an inner code block that surfaces typed ETL exceptions and an outer catch-all to keep documented exception contracts intact"
key_files_created: []
key_files_modified:
  - tests/v1/engine/components/control/test_send_mail.py
  - src/v1/engine/components/control/send_mail.py
decisions:
  - "BUG-MAIL-001: attachment ETLError swallowed by outer except blocks -- fixed at source via ``except ETLError: raise`` guard, not via test-side workaround (project memory: rewrite over patch / fix source no fallbacks)"
  - "Generic-Exception attachment branch covered via passing a directory path (IsADirectoryError, OSError subclass that does NOT match FileNotFoundError so it lands in the inner ``except Exception``) -- avoids relying on filesystem permission state which varies across CI environments"
  - "ASCII-log enforcement applied to both happy path AND error path tests via the assert_ascii_logs fixture from Plan 14-01 root conftest"
metrics:
  duration_minutes: ~30
  send_mail_pct_before: 60.2
  send_mail_pct_after: 100.0
  send_mail_missed_lines_before: 49
  send_mail_missed_lines_after: 0
  control_subsystem_pct_before: 65.7
  control_subsystem_pct_after: 98.6
  tests_added: 32
  tests_total_after: 37
  bugs_fixed: 1
---

# Phase 14 Plan 03: Engine Control Subsystem Summary

**One-liner:** Lifted `src/v1/engine/components/control/send_mail.py` from 60.2% to 100.0% line coverage (49 -> 0 missed lines) via 32 new boundary-mocked unit tests covering SSL/STARTTLS/plain SMTP, attachments, die_on_error modes, and the catch-all Exception branch -- and surfaced + fixed BUG-MAIL-001 (attachment `FileOperationError` was being silently rewrapped to `ComponentExecutionError` by the outer `except Exception` block, contradicting the documented contract).

## What Was Built

### tests/v1/engine/components/control/test_send_mail.py (extended +437 / -7 lines)

Six new test classes added on top of the existing two (`TestValidateConfigDeferred`, `TestProcessSmtpPort`):

1. **TestProcessSmtpPort** (extended) -- `test_process_below_range_smtp_port_raises` (smtp_port=0), `test_process_default_smtp_port_when_omitted` (None -> DEFAULT_SMTP_PORT=25).
2. **TestSmtpTransportBranches** -- `ssl=True` -> `smtplib.SMTP_SSL`; `starttls=True` + creds -> SMTP -> starttls() -> login() -> sendmail() -> quit() ordering; plain SMTP no-auth; auth-skip when only one of username/password is set.
3. **TestAttachments** -- real-file success (verifies MIME multipart includes filename + Content-Disposition); missing file under both `die_on_error` modes (FileOperationError vs warn-and-continue); generic OSError (directory path -> IsADirectoryError) under both `die_on_error` modes.
4. **TestSendFailureBranches** -- SMTPException via `mock_server.sendmail.side_effect`; OSError via `mock_smtp.side_effect`; ValueError via `sendmail.side_effect` to exercise the catch-all `except Exception` branch; both `die_on_error` modes.
5. **TestValidateConfigErrors** -- required-field errors (smtp_host, from_email); empty/non-list `to`; non-list cc/bcc/attachments parametrize; `_process` raise-on-validate-fail with joined error message.
6. **TestRecipientHandling** -- envelope to `sendmail()` = to + cc + bcc concatenation; Bcc absent from rendered headers (privacy semantics) but present in envelope; default empty cc/bcc -> envelope has only `to`.
7. **TestPublicValidateConfig** -- public `validate_config()` returns True on valid config; False on each missing-required field (parametrized).
8. **TestAsciiLogging** -- happy-path AND error-path log messages are ASCII (uses `assert_ascii_logs` fixture from Plan 14-01 root conftest).

### src/v1/engine/components/control/send_mail.py (BUG-MAIL-001 fix, +18 / -1 lines)

Inserted `except ETLError: raise` between the attachment-loop boundary and the SMTP-failure catch blocks. See "Deviations from Plan" -> "Auto-fixed Issues" below for the root-cause explanation.

## Tasks Completed

| Task | Status | Commit |
|------|--------|--------|
| 14-03-001 (SSL/STARTTLS/plain branches via smtplib boundary mock) | done | `1c24b76` |
| BUG-MAIL-001 (ETLError swallowed by outer except blocks) | done | `6b2b05c` |
| 14-03-002 (attachment + die_on_error + catch-all branches) | done | `d46907f` |
| 14-03-003 (per-module gate verification) | done | (no commit -- verification step) |

Total commits: 3. Plan's `commit_map` predicted 2-3; landed at 3 (the conditional BUG fix surfaced).

## Coverage Result

**send_mail.py:** 60.2% (123 stmts, 49 missed) -> **100.0% (125 stmts, 0 missed)**.

The +2 stmts is the new `except ETLError: raise` guard (one line for the except clause + one for the bare `raise`).

**Full subsystem (`src/v1/engine/components/control`):**

| Module | % Before (Phase 13) | % After (Plan 14-03) | Status |
|--------|--------------------:|---------------------:|--------|
| die.py | 96 | 95.7 | PASS |
| send_mail.py | 60 | 100.0 | PASS (lift target) |
| sleep.py | 100 | 100.0 | PASS |
| warn.py | 98 | 98.1 | PASS |

Per-module gate (`scripts/check_per_module_coverage.py cov_14_03.json --floor 95`): **PASS: all 4 in-scope modules at >= 95.0% line coverage.**

## Verification Evidence

- `python -m pytest tests/v1/engine/components/control/test_send_mail.py -q` -- 37 passed.
- `python -m pytest tests/v1/engine/components/control/ -n auto -q` -- 136 passed (full subsystem, 10 workers).
- `python -m pytest tests/v1/engine/components/control/ -n auto --cov=src/v1/engine/components/control --cov-report=json:cov_14_03.json -q` -- 136 passed, JSON written.
- `python scripts/check_per_module_coverage.py cov_14_03.json --floor 95` -- `PASS: all 4 in-scope modules at >= 95.0% line coverage`.
- All `pytest.raises` use ETLError subclasses (`ConfigurationError`, `FileOperationError`, `ComponentExecutionError`) -- never bare `Exception`.
- No new `# pragma: no cover` added (D-C3 allowlist not needed -- 100% reachable).
- No `inplace=True` introduced.
- ASCII-only log enforcement applied via `assert_ascii_logs` fixture in `TestAsciiLogging`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] BUG-MAIL-001: attachment `FileOperationError` swallowed by outer `except Exception`.**

- **Found during:** Task 14-03-002, while writing `test_attachment_missing_die_on_error_true_raises` and `test_attachment_unreadable_die_on_error_true_raises`. Both tests expected `FileOperationError` per the `_process` docstring contract ("Raises: FileOperationError: If attachment files cannot be read") but received `ComponentExecutionError("Unexpected error sending email: ...")` instead.
- **Issue:** The attachment loop's inner `except FileNotFoundError` and `except Exception` blocks correctly raise `FileOperationError`. However, those raises propagate up to the OUTER `try` surrounding the entire attachment-loop + SMTP-send block. The outer try has two catches:
  - `except (smtplib.SMTPException, ConnectionError, OSError)` -- catches `FileNotFoundError` (OSError subclass), but the inner `raise FileOperationError(...) from e` produces a `FileOperationError` instance, NOT a FileNotFoundError -- so this branch does NOT match. So far so good.
  - `except Exception` (catch-all) -- catches `FileOperationError` because it is an `Exception` subclass via `ETLError -> Exception`. The `FileOperationError` instance gets silently rewrapped to `ComponentExecutionError("Unexpected error sending email: <FileOperationError str>")`.

  Net effect: the documented `FileOperationError` contract was unreachable for any attachment failure when `die_on_error=True`. Callers got `ComponentExecutionError` -- a different exception type with a different `component_id`-prefixed message -- instead.
- **Fix:** Inserted `except ETLError: raise` between the attachment-loop boundary and the SMTP-failure catch blocks. This re-raises any `ETLError`-derived exception (`FileOperationError`, `ConfigurationError`, `ComponentExecutionError`) untouched, so attachment errors surface with their documented type and other ETL exceptions are not double-wrapped. Aligned with project memory rules `feedback_rewrite_over_patch` and `feedback_fix_source_no_fallbacks`: the fix is at the root cause (the `except Exception` is too broad), not a defensive shim downstream.
- **Files modified:** `src/v1/engine/components/control/send_mail.py` (+18 / -1).
- **Commit:** `6b2b05c` (`fix(14-03): BUG-MAIL-001 attachment ETLError swallowed by outer except blocks`).
- **Test impact:** All 6 attachment / die-on-error tests pass post-fix. No other test in the suite referenced `send_mail` (verified via `grep`), so no broader regression.

No other deviations. All other tasks executed exactly as the plan specified.

## D-C5 Outcome

The catch-all `except Exception` branch IS reachable (covered by `test_generic_exception_die_on_error_true_raises_component_error` and `test_generic_exception_die_on_error_false_swallows` via `ValueError` side-effect). No deletion needed; no pragma applied.

## Self-Check: PASSED

**Files verified to exist:**
- `tests/v1/engine/components/control/test_send_mail.py` -- FOUND (583 lines, 32 new tests added)
- `src/v1/engine/components/control/send_mail.py` -- FOUND (BUG-MAIL-001 fix applied)
- `.planning/phases/14-coverage-push-to-95-per-module-floor/14-03-SUMMARY.md` -- FOUND (this file)

**Commits verified to exist (3 commits, range 3c4be62..HEAD):**
- `1c24b76` test(14-03): COV-CTL-001 send_mail SSL/STARTTLS/plain branches via smtplib boundary mock -- FOUND
- `6b2b05c` fix(14-03): BUG-MAIL-001 attachment ETLError swallowed by outer except blocks -- FOUND
- `d46907f` test(14-03): COV-CTL-002 send_mail attachment + die_on_error + catch-all branches -- FOUND

**Verification gate (from PLAN.md):**
1. `send_mail.py` >= 95% line coverage -- 100.0% -- PASS.
2. All tests in `test_send_mail.py` pass; ASCII-log fixture clean -- 37 passed -- PASS.
3. No new pragma outside D-C3 allowlist -- VERIFIED via grep -- PASS.
4. All `pytest.raises` use specific ETLError subclasses -- VERIFIED (`ConfigurationError`, `FileOperationError`, `ComponentExecutionError`) -- PASS.
5. Per-module gate exits 0 for `src/v1/engine/components/control/` -- `PASS: all 4 in-scope modules at >= 95.0%` -- PASS.

All five verification-gate criteria GREEN. Plan 14-03 complete.
