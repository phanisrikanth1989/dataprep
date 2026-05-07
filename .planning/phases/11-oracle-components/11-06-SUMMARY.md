---
phase: 11-oracle-components
plan: 06
subsystem: converter
tags: [converter, oracle, needs-review, D-E1]
requires:
  - "Phase 11 plans 11-02..05 ship engine support for ORACLE_SID/SERVICE_NAME/RAC"
  - "Plan 11-04 raises ConfigurationError for ORACLE_OCI/ORACLE_WALLET unless thick_mode=true"
provides:
  - "Conditional needs_review for Wallet/OCI on the 3 in-scope Oracle converters"
  - "Zero needs_review for SID/SERVICE_NAME/RAC (engine ships them)"
affects:
  - src/converters/talend_to_v1/components/database/oracle_connection.py
  - src/converters/talend_to_v1/components/database/oracle_row.py
  - src/converters/talend_to_v1/components/database/oracle_output.py
  - tests/converters/talend_to_v1/components/database/test_oracle_connection.py
  - tests/converters/talend_to_v1/components/database/test_oracle_row.py
  - tests/converters/talend_to_v1/components/database/test_oracle_output.py
tech-stack:
  added: []
  patterns:
    - "Conditional needs_review in converter step 9 / 7 / 5 (gated on connection_type)"
key-files:
  created: []
  modified:
    - src/converters/talend_to_v1/components/database/oracle_connection.py
    - src/converters/talend_to_v1/components/database/oracle_row.py
    - src/converters/talend_to_v1/components/database/oracle_output.py
    - tests/converters/talend_to_v1/components/database/test_oracle_connection.py
    - tests/converters/talend_to_v1/components/database/test_oracle_row.py
    - tests/converters/talend_to_v1/components/database/test_oracle_output.py
decisions:
  - "Plan-aligned: SID/SERVICE_NAME/RAC emit zero needs_review (engine ships them in 11-02..05)"
  - "Plan-aligned: ORACLE_WALLET/ORACLE_OCI emit a single needs_review with severity=needs_review pointing at oracle_config.thick_mode"
  - "T-11-05 mitigation: needs_review message contains only the connection-type label and the thick_mode/Instant Client guidance -- no host, port, user, password, wallet path"
  - "The 6 deferred Oracle converters (oracle_input, oracle_sp, oracle_bulk_exec, oracle_commit, oracle_rollback, oracle_close) keep their engine_gap entries until their engines ship in later phases"
metrics:
  duration: "~10 min"
  completed: "2026-05-07"
  tasks: 2
  files_modified: 6
requirements: [ORAC-05]
---

# Phase 11 Plan 06: Converter D-E1 Wallet/OCI Conditional Review Summary

Convert the 3 in-scope Oracle converters (`oracle_connection`, `oracle_row`, `oracle_output`) from a flat `engine_gap` placeholder to a conditional `needs_review` entry per D-E1: Wallet and OCI flag thick-mode setup; SID/SERVICE_NAME/RAC convert clean.

## What Changed

### Converters (3 files)

Each converter's step that previously appended a single `engine_gap` entry now wraps the append in:

```python
if config["connection_type"] in ("ORACLE_WALLET", "ORACLE_OCI"):
    needs_review.append({
        "issue": (
            f"Connection type {config['connection_type']} requires "
            f"oracle_config.thick_mode=true in job config, plus Oracle "
            f"Instant Client on the host. Phase 11 raises ConfigurationError "
            f"until thick_mode is set."
        ),
        "component": node.component_id,
        "severity": "needs_review",
    })
```

- `oracle_connection.py`: step 9 (file commit `eef8c79`)
- `oracle_row.py`: step 7
- `oracle_output.py`: step 5

The existing 8 converter pipeline steps (parse params, schema extract, build_component_dict, etc.) are untouched.

### Tests (3 files)

`TestNeedsReview` class in each test file replaced with 6 methods:

| Method | Connection type | Expected |
|--------|-----------------|----------|
| test_no_needs_review_for_sid | ORACLE_SID | 0 entries |
| test_no_needs_review_for_service_name | ORACLE_SERVICE_NAME | 0 entries |
| test_no_needs_review_for_rac | ORACLE_RAC | 0 entries |
| test_needs_review_for_wallet | ORACLE_WALLET | 1 entry, severity=needs_review, contains "thick_mode" + "Instant Client" + "ORACLE_WALLET" |
| test_needs_review_for_oci | ORACLE_OCI | 1 entry, severity=needs_review, contains "thick_mode" + "Instant Client" + "ORACLE_OCI" |
| test_needs_review_message_no_secrets | ORACLE_WALLET with USER/PASS set | issue text contains no "scott", "tiger", "keystore" -- T-11-05 mitigation |

Old tests (`test_needs_review_count`, `test_needs_review_is_engine_gap`, `test_needs_review_message`, `test_needs_review_has_component_id`, `test_no_framework_param_needs_review`) removed -- they asserted the previous engine_gap behavior. The component_id assertion is folded into `test_needs_review_for_wallet`.

## Untouched

The 6 deferred Oracle converters (`oracle_input`, `oracle_sp`, `oracle_bulk_exec`, `oracle_commit`, `oracle_rollback`, `oracle_close`) and their tests are unchanged. They retain their `engine_gap` needs_review entries until each engine ships in a later phase.

## Verification

Acceptance criteria checked at commit time:

- `grep -c "No concrete engine implementation"` == 0 in oracle_connection.py / oracle_row.py / oracle_output.py
- `grep -c "ORACLE_WALLET\|ORACLE_OCI"` >= 1 (== 2) in each of the 3 converters
- `grep -c "thick_mode"` >= 1 (== 2) in each
- All 3 converters import cleanly
- The 6 deferred Oracle converters STILL have 1 `No concrete engine implementation` entry each
- `pytest tests/converters/talend_to_v1/components/database/ -x` -> 617 passed
- `pytest tests/converters/.../test_oracle_*.py::TestNeedsReview -v` -> 18 passed
- All 3 test files ASCII-clean (verified via `file <path>` -> "ASCII text")

### TDD gate compliance

Plan-level `tdd="true"` is on Task 2. Plan-level RED state was confirmed before committing Task 2: with the new converters in place but the old tests intact, `pytest TestNeedsReview` produced 10 failed / 3 passed (failures with `IndexError` from `result.needs_review[0]` and `assert 0 == 1`). After replacing `TestNeedsReview` with the new methods (commit `af04ed7`), all 18 tests pass GREEN. No REFACTOR pass needed.

Commit sequence on `worktree-agent-a690a8fc796854b13`:

| Commit | Type | Subject |
|--------|------|---------|
| eef8c79 | refactor | replace engine_gap with conditional Wallet/OCI thick-mode review (D-E1) |
| af04ed7 | test | TestNeedsReview asserts D-E1 conditional Wallet/OCI behavior |

The plan's task ordering (Task 1 converter -> Task 2 tests) inverts the strict RED/GREEN order, but the RED gate is verifiable (the test run shown above) and the plan explicitly directs this sequence in its `<action>` blocks.

## Threat Model

| Threat | Status |
|--------|--------|
| T-11-05 (Information Disclosure via needs_review text) | Mitigated. Message text only contains the connection-type label (ORACLE_WALLET / ORACLE_OCI) plus generic "thick_mode" / "Instant Client" guidance. `test_needs_review_message_no_secrets` asserts that USER/PASS values do not leak into the issue text. |

No new threat surface introduced by this plan -- the converter does not execute SQL or DDL.

## Deviations from Plan

### Auto-added Tests

**1. [Rule 2 - Critical mitigation] Added `test_needs_review_message_no_secrets`**
- **Found during:** Task 2 (test design)
- **Issue:** Plan documents T-11-05 mitigation in the threat model but doesn't list a corresponding test. Without an explicit assertion, future edits to the message string could regress the mitigation.
- **Fix:** Added a 6th test in each of the 3 test files: builds a node with USER='"scott"' and PASS='"tiger"', confirms the issue text contains neither value (and no "keystore" for the connection test).
- **Files modified:** test_oracle_connection.py, test_oracle_row.py, test_oracle_output.py
- **Commit:** af04ed7

### Other deviations

None. The 6 deferred Oracle converters stay at engine_gap; the 3 in-scope converters move to conditional needs_review.

## Auth Gates

None.

## Known Stubs

None. The Wallet/OCI engine support is intentionally deferred (out of phase 11 scope) and is documented as a needs_review entry, not a stub. SID/SERVICE_NAME/RAC are fully wired by the engine plans (11-02..05) in this same phase.

## Self-Check: PASSED

- src/converters/talend_to_v1/components/database/oracle_connection.py: FOUND
- src/converters/talend_to_v1/components/database/oracle_row.py: FOUND
- src/converters/talend_to_v1/components/database/oracle_output.py: FOUND
- tests/converters/talend_to_v1/components/database/test_oracle_connection.py: FOUND
- tests/converters/talend_to_v1/components/database/test_oracle_row.py: FOUND
- tests/converters/talend_to_v1/components/database/test_oracle_output.py: FOUND
- Commit eef8c79: FOUND
- Commit af04ed7: FOUND
